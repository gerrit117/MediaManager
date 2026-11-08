"""Per-user lifecycle notifications, durable outbox and browser Web Push."""
import base64,fcntl,hashlib,json,logging,secrets
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID,uuid4
from sqlalchemy import select,text
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from typing import Annotated,Literal
from media_manager.database import DbSessionDependency,get_session
from media_manager.auth.db import User
from media_manager.auth.users import current_active_user
from media_manager.media_features_models import NotificationPreference,PushSubscription,RequestState,Delivery
from media_manager.configuration import config_file
from media_manager.config import MediaManagerConfig
log=logging.getLogger(__name__)
router=APIRouter()
CATEGORIES=('request_created','request_approved','request_rejected','request_finished')
COPY={
 'de':{'request_created':('Neue Anfrage','Eine neue Medienanfrage ist eingegangen.'),'request_approved':('Anfrage angenommen','Deine Anfrage wurde angenommen.'),'request_rejected':('Anfrage abgelehnt','Deine Anfrage wurde abgelehnt.'),'request_finished':('Jetzt verfügbar','Deine Anfrage wurde importiert und ist jetzt in Emby verfügbar.')},
 'en':{'request_created':('New request','A new media request has arrived.'),'request_approved':('Request approved','Your request has been approved.'),'request_rejected':('Request declined','Your request has been declined.'),'request_finished':('Now available','Your request has been imported and is now available in Emby.')},
}
def now():return datetime.now(timezone.utc)
def preferences(db,user):
    record=db.get(NotificationPreference,user.id)
    return {k:(record.categories.get(k,{'email':True,'push':False}) if record else {'email':True,'push':False}) for k in CATEGORIES if k!='request_created' or user.is_superuser}
def enqueue(db,event_key,user,category,details):
    if not user.is_active or not user.is_verified:return
    choice=preferences(db,user).get(category,{})
    for channel in ['email','push']:
        if not choice.get(channel):continue
        if channel=='push' and not db.scalar(select(PushSubscription.id).where(PushSubscription.user_id==user.id).limit(1)):continue
        from sqlalchemy.dialects.postgresql import insert
        db.execute(insert(Delivery).values(id=uuid4(),event_key=event_key,user_id=user.id,channel=channel,payload={'category':category,'details':details},attempts=0,next_attempt=now()).on_conflict_do_nothing(index_elements=['event_key','user_id','channel']))


def requests(db):
    from media_manager.movies.models import MovieRequest,Movie
    from media_manager.tv.models import SeasonRequest,Show,Season,Episode
    from media_manager.library_models import EpisodeRequest
    for request,media in db.execute(select(MovieRequest,Movie).join(Movie,MovieRequest.movie_id==Movie.id)):yield 'movie',request,media,None,None
    for request,season,media in db.execute(select(SeasonRequest,Season,Show).join(Season,SeasonRequest.season_id==Season.id).join(Show,Season.show_id==Show.id)):yield 'season',request,media,season,None
    for request,episode,season,media in db.execute(select(EpisodeRequest,Episode,Season,Show).join(Episode,EpisodeRequest.episode_id==Episode.id).join(Season,Episode.season_id==Season.id).join(Show,Season.show_id==Show.id)):yield 'episode',request,media,season,episode

def describe(db,media,request,season=None,episode=None):
    user=db.get(User,request.requested_by_id) if request.requested_by_id else None
    return {'title':media.name,'year':media.year,'requester':user.email if user else '', 'season':season.number if season else None,'episode':episode.number if episode else None,'reason':''}

def observe(db,check_availability=True,baseline=False):
    from media_manager.emby import EmbyClient
    from media_manager.library_availability import season_presence
    from media_manager.movies.schemas import Movie as MovieDTO
    from media_manager.movies.service import MovieService
    # Build ordinary services using the same session; no download/import is triggered here.
    from media_manager.request_center import related_files
    from media_manager.movies.repository import MovieRepository
    from media_manager.tv.repository import TvRepository
    from media_manager.tv.service import TvService
    from media_manager.torrent.service import TorrentService
    from media_manager.torrent.repository import TorrentRepository
    from media_manager.indexer.service import IndexerService
    from media_manager.indexer.repository import IndexerRepository
    from media_manager.notification.service import NotificationService
    from media_manager.notification.repository import NotificationRepository
    shared=(TorrentService(TorrentRepository(db)),IndexerService(IndexerRepository(db)),NotificationService(NotificationRepository(db)))
    movies=MovieService(MovieRepository(db),*shared);tv=TvService(TvRepository(db),*shared)
    emby=EmbyClient();admins=list(db.scalars(select(User).where(User.is_superuser==True,User.is_active==True)).unique())
    for kind,request,media,season,episode in requests(db):
        record=db.get(RequestState,(kind,request.id));fresh=record is None
        if fresh:
            record=RequestState(kind=kind,request_id=request.id,state='pending',rejected=False,reason=None,emby_available=None,first_seen=now());db.add(record)
        details=describe(db,media,request,season,episode)
        if fresh and not baseline:
            for admin in admins:enqueue(db,f'{kind}:{request.id}:created',admin,'request_created',details)
        if record.rejected and not request.authorized:continue
        state='approved' if request.authorized else 'pending'
        if check_availability:
            if kind=='movie':downloaded=movies.is_movie_downloaded(MovieDTO.model_validate(media));required=None
            else:
                show=tv.tv_repository.get_show_by_id(media.id);sd=next(s for s in show.seasons if s.id==season.id)
                present=season_presence(tv,show,sd)
                required={episode.number} if episode else {ep.number for ep in sd.episodes if ep.air_date is None or ep.air_date<=now().astimezone(ZoneInfo('Europe/Berlin')).date()}
                downloaded=bool(required) and required<=present
            from media_manager.library_models import ShowExternalId
            aliases=list(db.scalars(select(ShowExternalId).where(ShowExternalId.show_id==media.id))) if kind!='movie' else []
            files=related_files(db,'movie' if kind=='movie' else 'tv',media,season,episode)
            expected=[p for f in files for p in (f.source_files or []) if Path(p).is_file()]
            available=emby.available(media,'movie' if kind=='movie' else 'tv',season.number if season else None,required,aliases,expected) if downloaded and not baseline else False
            record.emby_available=available
            if downloaded:state='finished' if available is True else 'waiting_emby'
        user=db.get(User,request.requested_by_id) if request.requested_by_id else None
        if user and not baseline:
            if request.authorized and (fresh or record.state=='pending'):
                enqueue(db,f'{kind}:{request.id}:approved',user,'request_approved',details)
            if state=='finished' and record.state not in ('finished','baseline_finished'):enqueue(db,f'{kind}:{request.id}:finished',user,'request_finished',details)
        record.state='baseline_finished' if (baseline or record.state=='baseline_finished') and state in ('finished','waiting_emby') else state
    db.commit()

def initialize():
    # First deployment establishes a baseline instead of emailing the historical request backlog.
    with next(get_session()) as db:
        if not db.get(RequestState,('system',UUID(int=0))):
            observe(db,baseline=True)
            db.add(RequestState(kind='system',request_id=UUID(int=0),state='initialized',rejected=False,reason=None,emby_available=None,first_seen=now()));db.commit()

def vapid():
    from py_vapid import Vapid
    path=config_file().parent/'webpush-private.pem'
    with open(config_file().parent/'.webpush.lock','a') as lock:
        Path(lock.name).chmod(0o600);fcntl.flock(lock,fcntl.LOCK_EX)
        if not path.exists():
            key=Vapid();key.generate_keys();key.save_key(str(path));path.chmod(0o600)
    key=Vapid.from_file(str(path))
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    public=base64.urlsafe_b64encode(key.public_key.public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)).decode().rstrip('=')
    return str(path),public

def valid_endpoint(endpoint):
    u=urlsplit(endpoint);host=(u.hostname or '').lower()
    suffixes=('push.services.mozilla.com','fcm.googleapis.com','web.push.apple.com','notify.windows.com','push.microsoft.com','wns.windows.com')
    return u.scheme=='https' and not u.username and not u.password and u.port in (None,443) and not u.fragment and any(host==s or host.endswith('.'+s) for s in suffixes)

def push_contact(config):
    sender=config.notifications.smtp_config.from_email
    if sender:return 'mailto:'+sender
    # The signing library requires an HTTPS contact hostname without an internal service port.
    host=urlsplit(str(config.misc.frontend_url)).hostname or ''
    if '.' in host and ':' not in host:return 'https://'+host
    return 'https://github.com'


def deliver(db):
    from media_manager.auth.mail import mail_ready
    from media_manager.notification.utils import send_email
    from media_manager.notification.template import render
    from pywebpush import webpush,WebPushException
    config=MediaManagerConfig()
    for item in db.scalars(select(Delivery).where(Delivery.sent_at==None,Delivery.next_attempt<=now(),Delivery.attempts<8).with_for_update(skip_locked=True).limit(30)):
        user=db.get(User,item.user_id);category=item.payload['category']
        if not user or not user.is_active or not preferences(db,user).get(category,{}).get(item.channel):item.sent_at=now();db.commit();continue
        language=user.preferred_language or 'de';title,body=COPY[language][category];details=item.payload['details']
        name=details['title']+(f" ({details['year']})" if details.get('year') else '')
        if details.get('season') is not None:name+=f" · S{details['season']:02d}"
        if details.get('episode') is not None:name+=f"E{details['episode']:02d}"
        text_body=body+' '+name+((' · '+details['reason']) if details.get('reason') else '')
        url='/web/dashboard'
        if item.channel=='email' and not mail_ready():item.next_attempt=now()+timedelta(minutes=5);db.commit();continue
        try:
            if item.channel=='email':
                fields={('Inhalt' if language=='de' else 'Title'):name}
                if category=='request_created':fields['Angefragt von' if language=='de' else 'Requested by']=details.get('requester','')
                if details.get('reason'):fields['Begründung' if language=='de' else 'Reason']=details['reason']
                send_email('MediaManager – '+title,render(title,escape(body),str(config.misc.frontend_url).rstrip('/')+url,language,fields),user.email)
            else:
                path,_=vapid();sent=set(item.payload.get('sent_devices',[]))
                for subscription in list(db.scalars(select(PushSubscription).where(PushSubscription.user_id==user.id))):
                    if str(subscription.id) in sent:continue
                    if not valid_endpoint(subscription.subscription['endpoint']):db.delete(subscription);continue
                    try:webpush(subscription_info=subscription.subscription,data=json.dumps({'title':title,'body':text_body,'url':url,'tag':item.event_key}),vapid_private_key=path,vapid_claims={'sub':push_contact(config)},timeout=15,ttl=86400)
                    except WebPushException as error:
                        if error.response is not None and error.response.status_code in (404,410):db.delete(subscription);continue
                        raise
                    sent.add(str(subscription.id));item.payload={**item.payload,'sent_devices':list(sent)};db.commit()
            item.sent_at=now();item.error=None
        except Exception as error:
            item.attempts+=1;item.error=type(error).__name__;item.next_attempt=now()+timedelta(minutes=min(360,2**item.attempts))
            log.warning('Notification delivery failed (%s), attempt %s.',type(error).__name__,item.attempts)
        db.commit()

def tick():
    from media_manager.release_control import run_pending_replacements
    with next(get_session()) as db:
        with db.get_bind().connect() as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(194731, 711)')):return
            try:run_pending_replacements();observe(db);deliver(db)
            except Exception:db.rollback();log.exception('Request notification processing failed.')
            finally:connection.execute(text('SELECT pg_advisory_unlock(194731, 711)'))

class Channels(BaseModel):
    email:bool=True
    push:bool=False
class Preferences(BaseModel):
    categories:dict[str,Channels]
@router.get('/preferences')
def get_preferences(db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    _,public=vapid()
    return {'categories':preferences(db,user),'vapid_public_key':public,'devices':len(list(db.scalars(select(PushSubscription.id).where(PushSubscription.user_id==user.id))))}
@router.put('/preferences')
def set_preferences(body:Preferences,db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    allowed=set(preferences(db,user))
    if not set(body.categories)<=allowed:raise HTTPException(400,'Unknown notification category.')
    row=db.get(NotificationPreference,user.id)
    if row is None:row=NotificationPreference(user_id=user.id,categories={});db.add(row)
    row.categories={**row.categories,**{k:v.model_dump() for k,v in body.categories.items()}};db.commit();return {'saved':True}
class Subscription(BaseModel):
    endpoint:str=Field(max_length=2048)
    keys:dict[str,str]
@router.post('/push')
def subscribe(body:Subscription,db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    try:
        if not valid_endpoint(body.endpoint):raise ValueError()
        for k,length in [('p256dh',65),('auth',16)]:
            value=body.keys[k]
            if len(value)>150 or len(base64.urlsafe_b64decode(value+'='*(-len(value)%4)))!=length:raise ValueError()
    except (ValueError,KeyError):raise HTTPException(400,'Invalid browser push subscription.') from None
    digest=hashlib.sha256(body.endpoint.encode()).hexdigest();row=db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash==digest))
    if row and row.user_id!=user.id:raise HTTPException(409,'Disable push for the previous account on this device first.')
    if row:row.subscription=body.model_dump()
    else:
        if len(list(db.scalars(select(PushSubscription.id).where(PushSubscription.user_id==user.id))))>=10:raise HTTPException(409,'Device limit reached.')
        db.add(PushSubscription(id=uuid4(),user_id=user.id,endpoint_hash=digest,subscription=body.model_dump()))
    db.commit();return {'saved':True}
class RemoveSubscription(BaseModel):endpoint:str
@router.delete('/push')
def unsubscribe(body:RemoveSubscription,db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    row=db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash==hashlib.sha256(body.endpoint.encode()).hexdigest(),PushSubscription.user_id==user.id))
    if row:db.delete(row);db.commit()
    return {'saved':True}
