import json,os,tomllib
from unittest.mock import patch,Mock
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from media_manager import configuration as cfg
from media_manager.config import MediaManagerConfig

@pytest.fixture
def settings(tmp_path,monkeypatch):
 monkeypatch.setenv('CONFIG_FILE',str(tmp_path/'config.toml'))
 monkeypatch.setattr('media_manager.config.config_path',tmp_path/'config.toml')
 monkeypatch.setitem(MediaManagerConfig.model_config,'toml_file',tmp_path/'config.toml')
 (tmp_path/'config.toml').write_text('[torrents.sabnzbd]\napi_key="private-existing-value"\n')
 return tmp_path

def test_staged_changes_do_not_affect_live_until_activation(settings):
 cfg.stage_settings({'torrents.sabnzbd.api_key':'','metadata.tmdb.default_language':'de'})
 assert MediaManagerConfig().metadata.tmdb.default_language=='en'
 assert cfg.settings_file(True).stat().st_mode&0o777==0o600
 cfg.activate_settings()
 assert MediaManagerConfig().metadata.tmdb.default_language=='de'
 assert MediaManagerConfig().torrents.sabnzbd.api_key=='private-existing-value'
 assert 'private-existing-value' not in json.dumps(cfg.fields_for_browser())
 cfg.stage_settings({'metadata.tmdb.default_language':'fr'});cfg.activate_settings()
 assert cfg.settings_file().with_suffix('.json.bak').exists()
 assert MediaManagerConfig().metadata.tmdb.default_language=='fr'

@pytest.mark.parametrize('changes',[{'database.password':123},{'database.port':0},{'misc.movie_directory':'relative'},{'auth.token_secret':'hack'},{'torrents.qbittorrent.enabled':True,'torrents.transmission.enabled':True}])
def test_invalid_settings_never_written(settings,changes):
 with pytest.raises(ValueError):cfg.stage_settings(changes)
 assert not cfg.settings_file(True).exists()

def test_environment_is_readonly(settings,monkeypatch):
 monkeypatch.setenv('MEDIAMANAGER_DATABASE__HOST','envdb')
 with pytest.raises(ValueError):cfg.stage_settings({'database.host':'different'})
 assert next(f for f in cfg.fields_for_browser() if f['key']=='database.host')['environment']

def test_settings_auth_boundary(settings):
 from media_manager.settings_router import router
 from media_manager.auth.users import current_superuser
 app=FastAPI();app.include_router(router,prefix='/settings');c=TestClient(app)
 assert c.get('/settings').status_code==401
 app.dependency_overrides[current_superuser]=lambda:object()
 assert c.get('/settings').status_code==200
 assert c.put('/settings',json={'values':{}},headers={'origin':'https://foreign.invalid'}).status_code==403
 assert c.put('/settings',json={'values':{'metadata.tmdb.default_language':'de'}}).status_code==200

def test_bootstrap_requires_code_and_never_overwrites(settings,monkeypatch):
 from media_manager.onboarding import create_setup_app
 (settings/'config.toml').unlink()
 c=TestClient(create_setup_app())
 body=dict(code='wrong',database_host='db',database_name='db',database_user='user',database_password='private',admin_email='owner@example.com',admin_password='a sufficiently long password',movie_directory=str(settings/'movies'),tv_directory=str(settings/'tv'),download_directory=str(settings/'downloads'))
 assert c.post('/setup/complete',json=body).status_code==403
 body['code']=(settings/'setup-code').read_text()
 db=Mock();db.execute.return_value.fetchone.return_value=(None,)
 context=Mock();context.__enter__=Mock(return_value=db);context.__exit__=Mock(return_value=None)
 with patch('psycopg.connect',return_value=context):response=c.post('/setup/complete',json=body)
 assert response.status_code==200,response.text
 saved=tomllib.loads((settings/'config.toml').read_text())
 assert len(saved['auth']['token_secret'])==64
 assert saved['metadata']['tmdb']['default_language']=='de'
 assert (settings/'config.toml').stat().st_mode&0o777==0o600
 assert 'a sufficiently long password' not in (settings/'config.toml').read_text()
 assert c.post('/setup/complete',json=body).status_code==409

def test_hot_settings_apply_without_restart_and_cold_stays_pending(settings):
 result=cfg.stage_settings({'metadata.tmdb.default_language':'de'},apply_live=True)
 assert result['restart_required'] is False
 assert MediaManagerConfig().metadata.tmdb.default_language=='de'
 assert not cfg.settings_file(True).exists()
 result=cfg.stage_settings({'indexers.prowlarr.enabled':True,'database.host':'pending-db'},apply_live=True)
 assert MediaManagerConfig().indexers.prowlarr.enabled
 assert MediaManagerConfig().database.host=='localhost'
 assert result['restart_required']
 result=cfg.stage_settings({'indexers.prowlarr.enabled':False},apply_live=True)
 assert not MediaManagerConfig().indexers.prowlarr.enabled
 assert result['restart_required']
 cfg.activate_settings();assert MediaManagerConfig().database.host=='pending-db'
