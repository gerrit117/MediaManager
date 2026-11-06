from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.indexer.config import ReleasePolicyConfig
from media_manager.release_policy import rank,rejection,language,validate_selection,allowed_results
from media_manager.tv.monitor import should_search


def release(title,usenet=True):
 return IndexerQueryResult(title=title,download_url='http://localhost/own.nzb',seeders=0 if usenet else 8,flags=[],size=100,usenet=usenet,age=1,indexer='own fixture')

@pytest.fixture
def policy(monkeypatch):
 cfg=ReleasePolicyConfig(enabled=True)
 monkeypatch.setattr('media_manager.release_policy.MediaManagerConfig',lambda:SimpleNamespace(indexers=SimpleNamespace(release_policy=cfg)))
 return cfg


def test_language_precedes_resolution_and_quality_orders(policy):
 choices=[release('Own.English.2160p.WEB'),release('Own.German.720p.WEB'),release('Own.German.1080p.WEB'),release('Own.German.2160p.WEB')]
 assert [r.title for r in allowed_results(choices)]==[choices[3].title,choices[2].title,choices[1].title,choices[0].title]
 with pytest.raises(HTTPException):validate_selection(choices[0],choices[1:])
 with pytest.raises(HTTPException):validate_selection(choices[1],choices[2:])
 validate_selection(choices[0],[choices[0]]) # English is a fallback when German is absent.

@pytest.mark.parametrize('tag',['REMUX','BDREMUX','HDCAM','CAM','TS','TELESYNC','TC','MD','MicDubbed'])
def test_excluded_releases_never_qualify(policy,tag):
 r=release('Own.German.2160p.'+tag)
 assert rejection(r) is not None
 assert allowed_results([r])==[]
 with pytest.raises(HTTPException):validate_selection(r,[])


def test_good_audio_tags_and_unknown_language(policy):
 assert rejection(release('Own.German.1080p.DTS.LD.DL.WEB')) is None
 assert rejection(release('Own.MULTI.1080p.WEB')) is not None
 policy.allow_unknown_language=True
 assert rejection(release('Own.MULTI.1080p.WEB')) is None


def test_web_preference_order_changes_selection(policy):
 policy.languages=['en','de'];policy.resolutions=['1080p','2160p','720p']
 choices=[release('Own.German.2160p'),release('Own.English.2160p'),release('Own.English.1080p')]
 assert allowed_results(choices)[0].title==choices[2].title


def test_usenet_has_no_seeder_requirement(policy):
 assert len(allowed_results([release('Own.German.1080p',True),release('Own.German.1080p',False)]))==2


def test_episode_and_season_parser():
 assert release('Own.S03E07.German.1080p').season==[3]
 assert release('Own.S01-S03.German.1080p').season==[1,2,3]


def test_weekly_episodes_skip_future_old_present_and_pending():
 today=date(2026,11,6);ep=SimpleNamespace(number=2,air_date=today)
 assert should_search(ep,today,today,set(),set(),None)
 assert not should_search(ep,today,today,{2},set(),None)
 assert not should_search(ep,today,today,set(),{2},None)
 assert not should_search(ep,today,today,set(),set(),SimpleNamespace(status='submitting'))
 assert not should_search(ep,today,today,set(),set(),SimpleNamespace(status='uncertain'))
 assert should_search(ep,today,today,{2},set(),SimpleNamespace(status='imported')) # upgrade search
 ep.air_date=today+timedelta(days=7);assert not should_search(ep,today,today,set(),set(),None)
 ep.air_date=today-timedelta(days=7);assert not should_search(ep,today,today,set(),set(),None)
 ep.air_date=None;assert not should_search(ep,today,today,set(),set(),None)


def test_episode_import_does_not_require_future_episodes(tmp_path):
 from media_manager.tv.service import TvService
 service=TvService.__new__(TvService);service.get_root_season_directory=Mock(return_value=tmp_path)
 service.import_episode=Mock(return_value=True)
 season=SimpleNamespace(number=1,episodes=[SimpleNamespace(number=1),SimpleNamespace(number=2)])
 success,count=service.import_season(SimpleNamespace(),season,[],[],wanted_episodes=[1])
 assert success and count==1
 assert service.import_episode.call_count==1 and service.import_episode.call_args.kwargs['episode_number']==1


def test_episode_release_ranges_are_not_confused_with_single_episodes():
 from media_manager.library import episode_numbers
 assert episode_numbers(['Own.S01E01'],1)=={1}
 assert episode_numbers(['Own.S01E01-E03.German.1080p'],1)=={1,2,3}
 assert episode_numbers(['Own.S01E01E02.German.1080p'],1)=={1,2}
 assert episode_numbers(['Own.S01E01.E02.German.1080p'],1)=={1,2}


def test_final_transport_gate_blocks_disallowed_manual_or_automatic_download(policy):
 from media_manager.torrent.manager import DownloadManager
 manager=DownloadManager.__new__(DownloadManager);manager._get_appropriate_client=Mock()
 with pytest.raises(HTTPException):manager.download(release('Own.German.2160p.REMUX'))
 manager._get_appropriate_client.assert_not_called()


def test_partial_indexer_search_cannot_enable_english_fallback(policy,monkeypatch):
 from media_manager.indexer.service import IndexerService
 monkeypatch.setattr('media_manager.indexer.service.MediaManagerConfig',lambda:SimpleNamespace(indexers=SimpleNamespace(release_policy=policy)))
 service=IndexerService.__new__(IndexerService);source=Mock();source.search.side_effect=RuntimeError('own failed source');service.indexers=[source];service.repository=Mock()
 with pytest.raises(HTTPException) as error:service.search('Own.S01E02',True)
 assert error.value.status_code==503


def test_manual_download_route_rechecks_scoring_and_priority(policy,monkeypatch):
 from media_manager.movies.service import MovieService
 monkeypatch.setattr('media_manager.movies.service.MediaManagerConfig',lambda:SimpleNamespace(indexers=SimpleNamespace(release_policy=policy)))
 service=MovieService.__new__(MovieService);service.indexer_service=Mock();service.torrent_service=Mock()
 selected=release('Own.English.2160p.WEB');german=release('Own.German.720p.WEB')
 service.indexer_service.get_result.return_value=selected
 service.get_all_available_torrents_for_movie=Mock(return_value=[selected,german])
 monkeypatch.setattr('media_manager.movies.service.evaluate_indexer_query_results',lambda r,*a,**k:r)
 with pytest.raises(HTTPException):service.download_torrent(uuid4(),SimpleNamespace(id=uuid4()))
 service.torrent_service.download.assert_not_called()


def test_missing_indexer_cannot_verify_fallback(policy,monkeypatch):
 from media_manager.indexer.service import IndexerService
 monkeypatch.setattr('media_manager.indexer.service.MediaManagerConfig',lambda:SimpleNamespace(indexers=SimpleNamespace(release_policy=policy)))
 service=IndexerService.__new__(IndexerService);service.indexers=[];service.repository=Mock()
 with pytest.raises(HTTPException):service.search('Own',True)
 policy.enabled=False
 assert service.search('Own',True)==[]
