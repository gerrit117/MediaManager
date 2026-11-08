"""Regressions for data preservation, private delivery and strict Emby confirmation."""
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch,Mock
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from media_manager.database import Base
from media_manager.media_features_models import ReleaseLock,Replacement,NotificationPreference,Delivery,RequestState
from media_manager.movies.models import Movie,MovieRequest
from media_manager.tv.models import Show,Season,Episode
from media_manager.auth.db import User
from media_manager.emby import EmbyClient,playable
from media_manager.release_control import locked,plan,finalize
from media_manager.account_notifications import enqueue,preferences,valid_endpoint,observe

@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name!='indexer_query_result'])
    with Session(engine) as session:yield session

def user(db,admin=False):
    row=User(id=uuid4(),email=str(uuid4())+'@example.com',hashed_password='test',is_active=True,is_verified=True,is_superuser=admin,preferred_language='de');db.add(row);db.commit();return row

def test_preferences_private_categories_and_deduplication(db):
    normal=user(db);admin=user(db,True)
    assert 'request_created' not in preferences(db,normal)
    assert 'request_created' in preferences(db,admin)
    enqueue(db,'request1',normal,'request_approved',{'title':'Own fixture','year':2026});db.commit()
    enqueue(db,'request1',normal,'request_approved',{'title':'Own fixture','year':2026});db.commit()
    assert len(list(db.scalars(select(Delivery))))==1
    db.add(NotificationPreference(user_id=normal.id,categories={'request_rejected':{'email':False,'push':False}}));db.commit()
    enqueue(db,'request2',normal,'request_rejected',{'title':'Own fixture'});db.commit()
    assert len(list(db.scalars(select(Delivery))))==1

@pytest.mark.parametrize('endpoint',['http://fcm.googleapis.com/x','https://localhost/x','https://127.0.0.1/x','https://fcm.googleapis.com.attacker.test/x','https://user:pass@fcm.googleapis.com/x','https://fcm.googleapis.com:444/x'])
def test_push_cannot_target_private_or_arbitrary_endpoints(endpoint):assert not valid_endpoint(endpoint)
@pytest.mark.parametrize('endpoint',['https://fcm.googleapis.com/fcm/send/x','https://updates.push.services.mozilla.com/wpush/v2/x','https://web.push.apple.com/Qx'])
def test_standard_browser_push_hosts(endpoint):assert valid_endpoint(endpoint)

def test_parent_protection_and_explicit_manual_override(db,tmp_path):
    show=Show(id=uuid4(),external_id=999,metadata_provider='tmdb',name='Own fixture',overview='',year=2026);db.add(show);db.flush()
    season=Season(id=uuid4(),show_id=show.id,number=1,external_id=998,name='Own season',overview='');db.add(season);db.flush()
    episode=Episode(id=uuid4(),season_id=season.id,number=1,external_id=997,title='Own episode');db.add(episode);db.add(ReleaseLock(kind='show',media_id=show.id));db.commit()
    assert locked(db,'season',season.id) and locked(db,'episode',episode.id)
    old=tmp_path/'Old.mkv';old.write_bytes(b'own fixture')
    with patch('media_manager.release_control.roots',return_value=[tmp_path]):
        with pytest.raises(__import__('fastapi').HTTPException):plan(db,'show',show.id,[old],True,False,[('episode',episode.id)])
    assert plan(db,'show',show.id,[],True,False,[('episode',episode.id)])['old_files']==[]
    assert plan(db,'show',show.id,[],True,True,[('episode',episode.id)])['old_files']==[]

@pytest.mark.parametrize('valid',[True,False])
def test_replacement_preserves_original_until_validated(db,tmp_path,valid):
    old=tmp_path/'Old.mkv';old.write_bytes(b'own original fixture');new=tmp_path/'New.mkv';new.write_bytes(b'own replacement fixture')
    from media_manager.release_control import fingerprint
    job=uuid4();row=Replacement(job_id=job,kind='movie',media_id=uuid4(),manifest={'old_files':[fingerprint(old)],'archived_files':[]},status='pending');db.add(row);db.commit()
    with patch('media_manager.release_control.roots',return_value=[tmp_path]),patch('media_manager.release_control.verified_video',return_value=valid):
        if valid:
            finalize(db,job,[str(new)]);assert not old.exists();archive=tmp_path/'.mediamanager-replaced'/str(job)/'Old.mkv';assert archive.read_bytes()==b'own original fixture';assert new.exists();assert row.status=='completed'
            finalize(db,job,[str(new)]) # idempotent
        else:
            with pytest.raises(ValueError):finalize(db,job,[str(new)])
            assert old.read_bytes()==b'own original fixture' and new.exists()

def test_changed_original_is_never_archived(db,tmp_path):
    from media_manager.release_control import fingerprint
    old=tmp_path/'Old.mkv';old.write_bytes(b'old');manifest={'old_files':[fingerprint(old)],'archived_files':[]};old.write_bytes(b'changed')
    new=tmp_path/'New.mkv';new.write_bytes(b'new');job=uuid4();db.add(Replacement(job_id=job,kind='movie',media_id=uuid4(),manifest=manifest,status='pending'));db.commit()
    with patch('media_manager.release_control.roots',return_value=[tmp_path]),patch('media_manager.release_control.verified_video',return_value=True):
        with pytest.raises(ValueError):finalize(db,job,[str(new)])
    assert old.read_bytes()==b'changed'

def test_atomic_import_failure_keeps_target(tmp_path):
    from media_manager.torrent.utils import import_file
    target=tmp_path/'old.mkv';target.write_bytes(b'old');source=tmp_path/'new.mkv';source.write_bytes(b'new')
    with patch.object(Path,'hardlink_to',side_effect=OSError),patch('shutil.copy2',side_effect=OSError):
        with pytest.raises(OSError):import_file(target,source)
    assert target.read_bytes()==b'old';assert source.read_bytes()==b'new'

def test_emby_requires_physical_media_and_exact_provider_id():
    media=SimpleNamespace(metadata_provider='tmdb',external_id=123)
    config=SimpleNamespace(enabled=True,url='http://emby:8096',api_key='own-test-key')
    client=EmbyClient(config)
    with patch.object(client,'items',return_value=[{'Id':'1','ProviderIds':{'Tmdb':'999'},'Path':'/movies/a.mkv'}]):assert client.available(media,'movie') is False
    client=EmbyClient(config)
    with patch.object(client,'items',return_value=[{'Id':'1','ProviderIds':{'Tmdb':'123'},'IsVirtualItem':True,'Path':'/movies/a.mkv'}]):assert client.available(media,'movie') is False
    client=EmbyClient(config)
    with patch.object(client,'items',side_effect=ValueError):assert client.available(media,'movie') is None

def test_emby_episode_completion_requires_every_requested_episode():
    media=SimpleNamespace(metadata_provider='tvdb',external_id=123);client=EmbyClient(SimpleNamespace(enabled=True))
    series=[{'Id':'1','ProviderIds':{'Tvdb':'123'}}];episodes=[{'Id':'e','ParentIndexNumber':1,'IndexNumber':1,'Path':'/tv/S01E01.mkv'}]
    with patch.object(client,'items',side_effect=[series,episodes]):assert client.available(media,'tv',1,{1,2}) is False
    client=EmbyClient(SimpleNamespace(enabled=True))
    with patch.object(client,'items',side_effect=[series,episodes]):assert client.available(media,'tv',1,{1}) is True

def test_mail_layout_escapes_dynamic_fields():
    from media_manager.notification.template import render
    result=render('<evil>','Own message',details={'Title':'<script>alert(1)</script>'})
    assert 'cid:mediamanager-logo' in result and 'mm-email-layout' in result
    assert '<script>' not in result and '&lt;evil&gt;' in result

def test_observer_only_finishes_after_emby_confirmation_and_sends_once(db):
    from media_manager.torrent.schemas import Quality
    from media_manager.account_notifications import observe
    owner=user(db);admin=user(db,True)
    media=Movie(id=uuid4(),external_id=123,metadata_provider='tmdb',name='Own lifecycle fixture',overview='',year=2026);db.add(media);db.flush()
    row=MovieRequest(id=uuid4(),movie_id=media.id,requested_by_id=owner.id,wanted_quality=Quality.fullhd,min_quality=Quality.hd,authorized=False);db.add(row);db.commit()
    with patch('media_manager.movies.service.MovieService.is_movie_downloaded',return_value=False):observe(db)
    assert db.get(RequestState,('movie',row.id)).state=='pending'
    assert len(list(db.scalars(select(Delivery))))==1
    row.authorized=True;db.commit()
    with patch('media_manager.movies.service.MovieService.is_movie_downloaded',return_value=False):observe(db)
    assert len(list(db.scalars(select(Delivery))))==2
    with patch('media_manager.movies.service.MovieService.is_movie_downloaded',return_value=True),patch('media_manager.emby.EmbyClient.available',return_value=False):observe(db)
    assert db.get(RequestState,('movie',row.id)).state=='waiting_emby'
    assert len(list(db.scalars(select(Delivery))))==2
    with patch('media_manager.movies.service.MovieService.is_movie_downloaded',return_value=True),patch('media_manager.emby.EmbyClient.available',return_value=True):observe(db);observe(db)
    assert db.get(RequestState,('movie',row.id)).state=='finished'
    assert len(list(db.scalars(select(Delivery))))==3

def test_emby_identity_matching_rejects_conflicting_ids():
    from media_manager.emby_matching import identity_match
    ids={'tmdb':'123','imdb':'tt123'}
    assert identity_match(ids,{'ProviderIds':{'Tmdb':'123','Imdb':'tt123'}})
    assert not identity_match(ids,{'ProviderIds':{'Tmdb':'999','Imdb':'tt123'}})
    assert not identity_match(ids,{'Name':'Same title','ProviderIds':{}})

def test_emby_old_filename_does_not_confirm_a_new_import():
    from media_manager.emby import path_matches
    assert not path_matches({'Path':'/emby/movies/Old.mkv'},['/data/movies/New-MANUAL-123.mkv'])
    assert path_matches({'Path':'/emby/movies/New-MANUAL-123.mkv'},['/data/movies/New-MANUAL-123.mkv'])
