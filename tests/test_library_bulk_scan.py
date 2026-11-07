from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from media_manager.library_scan import read_nfo,source_index,build_show,lock_scan,read_status,run_scan
from media_manager.library_scan_config import LibraryScanConfig


def test_nfo_id_is_explicit_and_xml_entities_are_not_processed(tmp_path):
 (tmp_path/'film.nfo').write_text('<movie><title>Own</title><year>2026</year><uniqueid type="tmdb">123</uniqueid></movie>')
 assert read_nfo(tmp_path,'movies')['external_id']==123
 (tmp_path/'film.nfo').write_text('<!DOCTYPE x [<!ENTITY e "no">]><movie><tmdbid>123</tmdbid></movie>')
 assert read_nfo(tmp_path,'movies') is None
 (tmp_path/'film.nfo').write_text('<movie><title>Own</title></movie>')
 assert read_nfo(tmp_path,'movies') is None


def test_arr_path_mapping_is_exact_and_duplicate_names_require_review(monkeypatch):
 cfg=LibraryScanConfig(radarr_url='http://localhost',radarr_api_key='own fixture')
 monkeypatch.setattr('media_manager.library_scan.source_json',lambda *a:[{'path':'/media/Own'},{'path':'/else/Other'},{'path':'/media/../secret'},{'path':'/media/nested/Deep'},{'path':'/media/Own'}])
 assert source_index(cfg,'radarr')=={'Own':None}


def test_show_metadata_includes_airdates_and_stable_episode_identity():
 entry={'tvdbId':123,'title':'Own','year':2026,'ended':False}
 episodes=[{'seasonNumber':1,'episodeNumber':1,'tvdbId':234,'title':'Own pilot','airDate':'2026-11-06'}]
 a=build_show(entry,episodes);b=build_show(entry,episodes)
 assert a.id==b.id and a.seasons[0].episodes[0].id==b.seasons[0].episodes[0].id
 assert str(a.seasons[0].episodes[0].air_date)=='2026-11-06'
 assert not a.continuous_download


def test_job_lock_and_restart_detection(tmp_path,monkeypatch):
 monkeypatch.setattr('media_manager.library_scan.config_file',lambda:tmp_path/'config.toml')
 from media_manager.configuration import atomic_json
 atomic_json(tmp_path/'library-scan-status.json',{'status':'running','processed':1})
 lease=lock_scan()
 with pytest.raises(HTTPException):lock_scan()
 assert read_status()['status']=='running'
 lease.close()
 assert read_status()['status']=='interrupted'


def test_source_urls_cannot_expose_keys_or_send_credentials_to_redirects():
 for url in ['file:///etc/passwd','http://user:password@example.com','http://example.com?apikey=secret']:
  with pytest.raises(ValueError):LibraryScanConfig(sonarr_url=url)


def test_source_validation_errors_hide_api_keys():
    with pytest.raises(ValueError) as error:LibraryScanConfig(sonarr_url='file:///invalid',sonarr_api_key='never-echo-this-fixture-key')
    assert 'never-echo-this-fixture-key' not in str(error.value)


def test_status_reader_does_not_overwrite_a_worker_that_just_finished(tmp_path,monkeypatch):
 import json
 from media_manager.configuration import atomic_json
 monkeypatch.setattr('media_manager.library_scan.config_file',lambda:tmp_path/'config.toml')
 status=tmp_path/'library-scan-status.json';atomic_json(status,{'status':'running','processed':1})
 def after_worker_finished():
  atomic_json(status,{'status':'completed','processed':2})
  return Mock()
 monkeypatch.setattr('media_manager.library_scan.lock_scan',after_worker_finished)
 assert read_status()['status']=='completed'
 assert json.loads(status.read_text())['status']=='completed'


def test_interruption_detection_cannot_overwrite_a_new_job(tmp_path,monkeypatch):
 import json
 from media_manager.configuration import atomic_json
 monkeypatch.setattr('media_manager.library_scan.config_file',lambda:tmp_path/'config.toml')
 status=tmp_path/'library-scan-status.json';atomic_json(status,{'status':'running','started_at':'old'})
 probe=Mock()
 probe.close.side_effect=lambda:atomic_json(status,{'status':'running','started_at':'new'})
 monkeypatch.setattr('media_manager.library_scan.lock_scan',lambda:probe)
 assert read_status()['status']=='interrupted'
 assert json.loads(status.read_text())=={'status':'running','started_at':'new'}
