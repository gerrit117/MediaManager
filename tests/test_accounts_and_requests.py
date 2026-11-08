import asyncio,logging
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock,patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from media_manager.database import Base,get_session
from media_manager.auth.db import User
from media_manager.auth.password_policy import validate_password
from media_manager.auth.request_policy import RequestUsage,apply_request_policy,usage_count
from media_manager.auth.security_models import Invitation
from media_manager.auth.users import current_superuser
from media_manager.auth.invitations import router
from media_manager.tv.models import Show,Season,Episode,SeasonRequest
from media_manager.library_models import EpisodeRequest
from media_manager.movies.models import Movie

@pytest.mark.parametrize('password',['Abcdef1!','Abcdef1_','Äbcdef1!'])
def test_password_allowed(password):validate_password(password)
@pytest.mark.parametrize('password',['Abcde1!','abcdef1!','ABCDEF1!','Abcdefg!','Abcdefg1','Abcdef1 '])
def test_password_rejected(password):
    with pytest.raises(ValueError):validate_password(password)

@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name!="indexer_query_result"])
    with Session(engine) as db:yield db
    engine.dispose()

def account(db,**fields):
    u=User(id=uuid4(),email=str(uuid4())+'@example.com',hashed_password='unused',is_active=True,is_verified=True,is_superuser=False,monthly_request_limit=1,auto_approve_requests=False,**fields);db.add(u);db.commit();return u

def test_season_and_episodes_share_one_lifetime_charge(db):
    u=account(db);s=Show(id=uuid4(),external_id=100,metadata_provider='tmdb',name='Own',overview='',year=2026);db.add(s);db.flush();season=Season(id=uuid4(),show_id=s.id,number=1,external_id=101,name='Own',overview='');db.add(season);db.flush();e1=Episode(id=uuid4(),season_id=season.id,number=1,external_id=102,title='Own1');e2=Episode(id=uuid4(),season_id=season.id,number=2,external_id=103,title='Own2');db.add_all([e1,e2]);db.commit()
    def charge(row,kind):apply_request_policy(db,row,kind);db.add(row);db.commit()
    from media_manager.torrent.schemas import Quality
    charge(EpisodeRequest(id=uuid4(),requested_by_id=u.id,episode_id=e1.id,wanted_quality=Quality.fullhd,min_quality=Quality.hd),'episodes');assert usage_count(db,u.id)==1
    charge(EpisodeRequest(id=uuid4(),requested_by_id=u.id,episode_id=e2.id,wanted_quality=Quality.fullhd,min_quality=Quality.hd),'episodes');assert usage_count(db,u.id)==1
    charge(SeasonRequest(id=uuid4(),requested_by_id=u.id,season_id=season.id,wanted_quality=Quality.fullhd,min_quality=Quality.hd),'tv');assert usage_count(db,u.id)==1
    row=db.scalar(select(RequestUsage).where(RequestUsage.user_id==u.id));row.created_at=datetime.now(timezone.utc)-timedelta(days=62);db.commit();assert usage_count(db,u.id)==0
    charge(EpisodeRequest(id=uuid4(),requested_by_id=u.id,episode_id=e2.id,wanted_quality=Quality.uhd,min_quality=Quality.hd),'episodes');assert usage_count(db,u.id)==0


def test_invitations_single_use_and_no_self_escalation(db):
    admin=account(db);admin.is_superuser=True;db.commit()
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_session]=lambda:db;app.dependency_overrides[current_superuser]=lambda:admin
    with patch('media_manager.auth.invitations.mail_ready',return_value=True),patch('media_manager.auth.invitations.send_verification') as sent,patch('media_manager.auth.invitations.notify_admins'):
        client=TestClient(app);code=client.post('/users/invitations',json={'email':'new@example.com'}).json()['code'];assert len(code)==5 and code.isalnum() and code==code.upper()
        payload={'email':'other@example.com','password':'Abcdef1!','invitation_code':code};assert client.post('/auth/register',json=payload).status_code==400
        payload.update(email='new@example.com',is_superuser=True,is_verified=True,monthly_request_limit=None,auto_approve_requests=True)
        r=client.post('/auth/register',json=payload);assert r.status_code==201,r.text;u=db.get(User,__import__('uuid').UUID(r.json()['id']));assert not u.is_verified and not u.is_superuser and not u.auto_approve_requests and u.monthly_request_limit==10
        assert client.post('/auth/register',json=payload).status_code==400
        assert sent.call_count==1
        listing=client.get('/users/invitations').json();assert 'code' not in str(listing) and 'digest' not in str(listing)
        assert client.post('/auth/register',json={'email':'nocode@example.com','password':'Abcdef1!'}).status_code==422


def test_expired_revoked_and_rate_limit(db):
    admin=account(db);admin.is_superuser=True;db.commit();app=FastAPI();app.include_router(router);app.dependency_overrides[get_session]=lambda:db;app.dependency_overrides[current_superuser]=lambda:admin
    with patch('media_manager.auth.invitations.mail_ready',return_value=True):
        c=TestClient(app);inv=c.post('/users/invitations',json={}).json();c.delete('/users/invitations/'+inv['id']);payload={'email':'new@example.com','password':'Abcdef1!','invitation_code':inv['code']};assert c.post('/auth/register',json=payload).status_code==400
        from uuid import UUID
        other=c.post('/users/invitations',json={}).json();expired=db.get(Invitation,UUID(other['id']));expired.expires_at=datetime.now(timezone.utc)-timedelta(days=1);db.commit()
        assert c.post('/auth/register',json=payload|{'invitation_code':other['code']}).status_code==400
        for _ in range(8):assert c.post('/auth/register',json=payload).status_code==400
        assert c.post('/auth/register',json=payload).status_code==429


def test_mail_hooks_never_log_tokens(caplog):
    from media_manager.auth.users import UserManager
    manager=UserManager(Mock());user=SimpleNamespace(id=uuid4(),email='own@example.com');secret='OWN-SYNTHETIC-SECRET-TOKEN'
    with patch('media_manager.auth.mail.mail_ready',return_value=True),patch('media_manager.auth.mail.send_link') as send:
        with caplog.at_level(logging.DEBUG):
            asyncio.run(manager.on_after_forgot_password(user,secret));asyncio.run(manager.on_after_request_verify(user,secret))
        assert secret not in caplog.text and send.call_count==2


def test_preview_and_request_do_not_add_to_visible_library(db):
    from media_manager.request_center import router as request_router
    from media_manager.auth.users import current_active_user
    from media_manager.movies.repository import MovieRepository
    from media_manager.movies.schemas import Movie as MovieDTO
    from media_manager.tv.schemas import Show as ShowDTO,Season as SeasonDTO,Episode as EpisodeDTO
    from media_manager.tv.repository import TvRepository
    from media_manager.torrent.schemas import Quality
    user=account(db)
    app=FastAPI();app.include_router(request_router);app.dependency_overrides[get_session]=lambda:db;app.dependency_overrides[current_active_user]=lambda:user
    provider=Mock(name='provider');provider.name='tmdb';provider.get_show_identifiers.return_value={}
    provider.get_movie_metadata.return_value=MovieDTO(external_id=123,metadata_provider='tmdb',name='Own new title',overview='Own',year=2026)
    provider.get_show_metadata.return_value=ShowDTO(external_id=456,metadata_provider='tmdb',name='Own show',overview='Own',year=2026,seasons=[SeasonDTO(number=1,external_id=457,name='Own season',overview='Own',episodes=[EpisodeDTO(number=n,external_id=457+n,title='Own episode') for n in [1,2]])])
    with patch('media_manager.request_center.get_metadata_provider',return_value=provider),patch('media_manager.request_center.notify_admins'):
        c=TestClient(app)
        assert c.get('/preview/movie/tmdb/123').status_code==200
        assert MovieRepository(db).get_movies()==[]
        r=c.post('/submit',json={'kind':'movie','external_id':123});assert r.status_code==201,r.text
        assert MovieRepository(db).get_movies()==[]
        movie=db.scalar(select(Movie).where(Movie.external_id==123));assert movie.request_only
        assert usage_count(db,user.id)==1
        # Same request is idempotent and does not charge again even at the limit.
        assert c.post('/submit',json={'kind':'movie','external_id':123}).status_code==201
        assert usage_count(db,user.id)==1
        # New season exceeds quota; its catalogue metadata remains hidden.
        r=c.post('/submit',json={'kind':'tv','external_id':456,'seasons':[1]});assert r.status_code==429,r.text
        assert TvRepository(db).get_shows()==[]
        feed=c.get('/center').json();assert len(feed['requests'])==1 and feed['requests'][0]['status']=='pending'
        other=account(db);app.dependency_overrides[current_active_user]=lambda:other
        assert c.get('/center').json()['requests']==[]


def test_mail_links_keep_tokens_out_of_http_urls():
    from media_manager.auth.mail import send_link
    from urllib.parse import urlsplit,parse_qs
    import re,html
    with patch('media_manager.auth.mail.send_email') as send:
        assert send_link('own@example.com','OWN-TEST-TOKEN','verify')
        target=html.unescape(re.search(r'href="([^"]+)"',send.call_args.args[1])[1]);url=urlsplit(target)
        assert not url.query and parse_qs(url.fragment)['token']==['OWN-TEST-TOKEN']


def test_smtp_tls_and_authentication_are_applied():
    import ssl
    from media_manager.notification.utils import send_email
    config=SimpleNamespace(notifications=SimpleNamespace(smtp_config=SimpleNamespace(smtp_host='test.invalid',smtp_port=587,smtp_user='own',smtp_password='own-test-secret',from_email='own@example.com',use_tls=True,use_ssl=False)))
    with patch('media_manager.notification.utils.MediaManagerConfig',return_value=config),patch('media_manager.notification.utils.smtplib.SMTP') as transport:
        server=transport.return_value.__enter__.return_value
        send_email('Own test','Own synthetic body','target@example.com')
        assert isinstance(server.starttls.call_args.kwargs['context'],ssl.SSLContext)
        server.login.assert_called_once_with('own','own-test-secret');server.sendmail.assert_called_once()
