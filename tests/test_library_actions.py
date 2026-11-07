from datetime import date,timedelta
from types import SimpleNamespace as NS
from uuid import uuid4
from unittest.mock import patch,Mock
import pytest,requests
from media_manager.library_availability import describe
from media_manager.movie_collections import tmdb_get,normalized_tmdb,normalized_radarr


def ep(number,air_date):return NS(id=uuid4(),number=number,external_id=number,title=str(number),air_date=air_date)


def test_episode_presence_future_and_undated_are_distinct():
 today=date(2026,11,7)
 season=NS(episodes=[ep(1,today-timedelta(days=7)),ep(2,today),ep(3,today+timedelta(days=7)),ep(4,None)])
 result=describe(season,{1},today=today,requested={2})
 assert [e['state'] for e in result['episodes']]==['available','missing','upcoming','unknown']
 assert result['available_count']==1 and result['missing_count']==1 and not result['downloaded']
 assert result['episodes'][1]['requested']
 assert describe(NS(episodes=[]),set(),today=today)['state']=='empty'
 assert describe(NS(episodes=season.episodes[:3]),{1,2},today=today)['downloaded']


def test_pending_and_failed_downloads_are_not_available():
 today=date.today();season=NS(episodes=[ep(1,today),ep(2,today)])
 result=describe(season,set(),today=today,pending={1},attention={2})
 assert [e['state'] for e in result['episodes']]==['downloading','attention']
 assert not result['downloaded'] and result['state']=='attention'


def test_tmdb_transport_never_exposes_secret_request_urls(caplog):
 key='tmdb-fixture-private'
 with patch('media_manager.movie_collections.requests.get',side_effect=requests.ConnectionError('https://api.themoviedb.org/?api_key='+key)):
  with pytest.raises(ValueError) as error:tmdb_get('collection/1',key)
  assert key not in str(error.value) and key not in caplog.text
 with patch('media_manager.movie_collections.requests.get',return_value=Mock(status_code=401)):
  with pytest.raises(ValueError,match='HTTP 401') as error:tmdb_get('collection/1',key)
  assert key not in str(error.value)
 with pytest.raises(ValueError,match='API key is required'):tmdb_get('collection/1','')


def test_tmdb_uses_documented_v3_endpoint_and_filters_credentials():
 response=Mock(status_code=200);response.json.return_value={'id':7}
 with patch('media_manager.movie_collections.requests.get',return_value=response) as get:
  assert tmdb_get('collection/7','private','de')=={'id':7}
  assert get.call_args.args==('https://api.themoviedb.org/3/collection/7',)
  assert get.call_args.kwargs['params']=={'api_key':'private','language':'de'}


def test_collection_sources_keep_members_but_do_not_trust_radarr_presence():
 data=normalized_radarr({'tmdbId':7,'title':'Collection','movies':[{'tmdbId':11,'title':'Part 1','year':2020,'isExisting':True,'imdbId':'tt123'}]})
 assert data['parts'][0]['tmdb_id']==11 and 'available' not in data['parts'][0]
 data=normalized_tmdb({'id':7,'name':'Collection','parts':[{'id':11,'title':'Part 1','release_date':'2020-01-01'},{'id':12,'title':'Future','release_date':''}]})
 assert data['parts'][0]['year']==2020 and data['parts'][1]['year'] is None


def test_rejected_episode_never_creates_a_submission_claim():
 from media_manager.episode_requests import submit_episode
 from media_manager.indexer.config import ReleasePolicyConfig
 from media_manager.indexer.schemas import IndexerQueryResult
 from fastapi import HTTPException
 result=IndexerQueryResult(title='Fixture.S01E02.German.1080p.MD',download_url='http://localhost/fixture.nzb',seeders=0,flags=[],size=1,usenet=True,age=1,indexer='Fixture')
 service=Mock();service.indexer_service.get_result.return_value=result
 with patch('media_manager.episode_requests.season_presence',return_value=set()),patch('media_manager.episode_requests.claimed_episodes',return_value=set()),patch('media_manager.release_policy.MediaManagerConfig',return_value=NS(indexers=NS(release_policy=ReleasePolicyConfig(enabled=True)))):
  with pytest.raises(HTTPException) as error:submit_episode(service,NS(id=uuid4()),NS(number=1,id=uuid4()),NS(number=2,id=uuid4()),result.id)
  assert error.value.status_code==409
 service.tv_repository.db.execute.assert_not_called()
 service.download_torrent.assert_not_called()
