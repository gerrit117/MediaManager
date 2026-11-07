import json
from types import SimpleNamespace as NS
from uuid import uuid4
from unittest.mock import Mock,patch
import pytest,requests
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from media_manager import discovery as d
from media_manager.auth.users import current_active_user
from media_manager.database import get_session

@pytest.fixture
def tmdb_config(monkeypatch):
 cfg=NS(metadata=NS(tmdb=NS(api_key='private-tmdb-fixture')))
 monkeypatch.setattr(d,'MediaManagerConfig',lambda:cfg);d._cache.clear();return cfg


def test_documented_lists_and_catalogue_filters_are_distinct():
 path,params=d.list_query('movie','trending','week',1,'DE',None,None,None,100)
 assert path=='trending/movie/week' and params=={}
 with pytest.raises(HTTPException):d.list_query('tv','trending','day',1,'DE',8,None,None,100)
 with pytest.raises(HTTPException):d.list_query('movie','trending','week',2,'DE',None,None,None,100)
 path,params=d.list_query('tv','top_rated','week',2,'DE',8,174,18,500)
 assert path=='discover/tv' and params['sort_by']=='vote_average.desc'
 assert params['with_watch_providers']=='8' and params['watch_region']=='DE'
 assert params['with_watch_monetization_types']=='flatrate' and params['with_companies']=='174'
 assert params['with_genres']=='18' and params['vote_count.gte']==500
 _,tv=d.list_query('tv','recent','week',1,'DE',None,None,None,50)
 _,movie=d.list_query('movie','recent','week',1,'DE',None,None,None,100)
 assert tv['sort_by']=='first_air_date.desc' and tv['first_air_date.gte']<tv['first_air_date.lte']
 assert movie['sort_by']=='primary_release_date.desc' and 'primary_release_date.lte' in movie


def test_existing_popular_titles_are_marked_instead_of_filtered_out():
 existing=str(uuid4());data={'results':[{'id':12,'name':'Well-known series','first_air_date':'2025-02-01','poster_path':'/poster.jpg'},{'id':13,'name':'New series','first_air_date':''},{'id':14,'name':'Adult item','adult':True}]}
 result=d.format_results(data,'tv',{12:existing})
 assert len(result)==2 and result[0]['added'] and result[0]['id']==existing
 assert result[0]['poster_path']=='https://image.tmdb.org/t/p/w500/poster.jpg'
 assert not result[1]['added'] and result[1]['year'] is None


def test_tvdb_aliases_open_the_original_series():
 db=Mock();canonical=uuid4();db.execute.side_effect=[[],[('249042',canonical)]]
 assert d.library_ids(db,'tv')=={249042:str(canonical)}


def test_cache_is_key_sensitive_but_does_not_store_keys_in_its_identifiers(tmdb_config):
 response=Mock(status_code=200);response.json.return_value={'results':[]}
 with patch.object(d.requests,'get',return_value=response) as get:
  d.tmdb('trending/movie/week',{'language':'de-DE'});d.tmdb('trending/movie/week',{'language':'de-DE'})
  assert get.call_count==1
  assert get.call_args.kwargs['params']['api_key']=='private-tmdb-fixture'
  assert 'private-tmdb-fixture' not in repr(list(d._cache))
  tmdb_config.metadata.tmdb.api_key='replacement-fixture';d.tmdb('trending/movie/week',{'language':'de-DE'})
  assert get.call_count==2


def test_errors_do_not_disclose_keys_or_remote_error_bodies(tmdb_config,caplog):
 with patch.object(d.requests,'get',side_effect=requests.ConnectionError('https://api.themoviedb.org/?api_key=private-tmdb-fixture')):
  with pytest.raises(HTTPException) as error:d.tmdb('trending/movie/week')
  assert error.value.status_code==502 and 'private-tmdb-fixture' not in error.value.detail+caplog.text
 with patch.object(d.requests,'get',return_value=Mock(status_code=401)):
  with pytest.raises(HTTPException) as error:d.tmdb('trending/movie/week')
  assert error.value.status_code==502 and 'API key' in error.value.detail
 tmdb_config.metadata.tmdb.api_key=''
 with pytest.raises(HTTPException) as error:d.tmdb('trending/movie/week')
 assert error.value.status_code==503


def test_discovery_authentication_validation_and_filter_forwarding(tmdb_config):
 app=FastAPI();app.include_router(d.router,prefix='/discover');client=TestClient(app)
 app.dependency_overrides[get_session]=lambda:Mock()
 assert client.get('/discover/movie').status_code==401
 app.dependency_overrides[current_active_user]=lambda:NS(is_superuser=False)
 with patch.object(d,'tmdb',return_value={'results':[{'id':1,'title':'A movie','release_date':'2020-01-01'}],'total_pages':9,'total_results':180,'page':1}) as remote,patch.object(d,'library_ids',return_value={}):
  response=client.get('/discover/movie?mode=popular&provider_id=8&company_id=174&region=DE&language=de')
  assert response.status_code==200,response.text
  assert remote.call_args.args[0]=='discover/movie'
  params=remote.call_args.args[1];assert params['with_watch_providers']=='8' and params['with_companies']=='174' and params['language']=='de-DE'
  assert 'private-tmdb-fixture' not in response.text
  assert client.get('/discover/movie?region=invalid').status_code==422
  assert client.get('/discover/movie?page=501').status_code==422
  assert client.get('/discover/tv?mode=trending&provider_id=8').status_code==422
