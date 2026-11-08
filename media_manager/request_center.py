"""Request-first catalogue workflow and per-account request progress."""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Annotated,Literal
from uuid import UUID,uuid4
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from media_manager.database import DbSessionDependency
from media_manager.auth.db import User
from media_manager.auth.users import current_active_user,current_superuser
from media_manager.auth.request_policy import apply_request_policy,usage_count,month_bounds
from media_manager.movies.models import Movie,MovieRequest,MovieFile
from media_manager.tv.models import Show,Season,Episode,SeasonRequest,SeasonFile,EpisodeDownload
from media_manager.library_models import EpisodeRequest
from media_manager.torrent.models import Torrent
from media_manager.torrent.schemas import Quality
from media_manager.tv.dependencies import tv_service_dep
from media_manager.movies.dependencies import movie_service_dep
from media_manager.metadataProvider.dependencies import get_metadata_provider
from media_manager.auth.mail import notify_admins
from media_manager.media_features_models import RequestState
from media_manager.config import MediaManagerConfig
router=APIRouter()

class Selection(BaseModel):
    kind:Literal['movie','tv']
    provider:Literal['tmdb','tvdb']='tmdb'
    external_id:int=Field(ge=1)
    language:Literal['de','en']='de'
    seasons:list[int]=Field(default_factory=list,max_length=100)
    episodes:dict[int,list[int]]=Field(default_factory=dict)
    wanted_quality:Quality=Quality.uhd
    min_quality:Quality=Quality.hd
    @model_validator(mode='after')
    def valid(self):
        if self.wanted_quality.value>self.min_quality.value:raise ValueError('Invalid quality range.')
        if any(n<0 for n in self.seasons) or any(n<0 for n in self.episodes):raise ValueError('Invalid season.')
        if sum(len(v) for v in self.episodes.values())>500:raise ValueError('Too many episodes.')
        return self

@router.get('/preview/{kind}/{provider}/{external_id}',dependencies=[Depends(current_active_user)])
def preview(kind:Literal['movie','tv'],provider:Literal['tmdb','tvdb'],external_id:int,language:Literal['de','en']='de'):
    metadata=get_metadata_provider(provider)
    try:media=metadata.get_movie_metadata(movie_id=external_id,language=language) if kind=='movie' else metadata.get_show_metadata(show_id=external_id,language=language)
    except Exception:raise HTTPException(502,'Could not load title metadata. Please try again.') from None
    if media is None:raise HTTPException(404,'Title not found.')
    return {'name':media.name,'year':media.year,'overview':media.overview,'seasons':[{'number':s.number,'name':s.name,'episodes':[{'number':e.number,'title':e.title,'air_date':e.air_date} for e in s.episodes]} for s in getattr(media,'seasons',[]) if s.episodes]}

@router.post('/submit',status_code=201)
def submit(body:Selection,db:DbSessionDependency,tv:tv_service_dep,movies:movie_service_dep,user:Annotated[User,Depends(current_active_user)],tasks:BackgroundTasks):
    provider=get_metadata_provider(body.provider)
    if body.kind=='tv' and not body.seasons and not body.episodes:raise HTTPException(400,'Select at least one season or episode.')
    # Resolve existing identities first; hidden catalogue records never become library entries here.
    if body.kind=='movie':
        media=db.scalar(select(Movie).where(Movie.external_id==body.external_id,Movie.metadata_provider==body.provider))
        if media is None:
            fresh=movies.add_movie(body.external_id,provider,body.language,request_only=True);media=db.get(Movie,fresh.id)
    else:
        fresh=tv.add_show(body.external_id,provider,body.language,request_only=True);media=db.get(Show,fresh.id)
    entries=[]
    if body.kind=='movie':entries=[(MovieRequest,'movies',{'movie_id':media.id})]
    else:
        for number in sorted(set(body.seasons)|set(body.episodes)):
            season=db.scalar(select(Season).where(Season.show_id==media.id,Season.number==number))
            if season is None:raise HTTPException(400,'Selected season is not available in the metadata.')
            if number in body.episodes:
                numbers=set(body.episodes[number])
                if not numbers:raise HTTPException(400,'Select at least one episode.')
                eps=list(db.scalars(select(Episode).where(Episode.season_id==season.id,Episode.number.in_(numbers))))
                if {e.number for e in eps}!=numbers:raise HTTPException(400,'Selected episode is not available in the metadata.')
                entries.extend((EpisodeRequest,'episodes',{'episode_id':e.id}) for e in eps)
            else:entries.append((SeasonRequest,'tv',{'season_id':season.id}))
    created=[]
    try:
        # Same account lock as all existing request routes: concurrent submissions share one quota.
        db.execute(select(User).where(User.id==user.id).with_for_update(of=User)).unique().scalar_one()
        for model,kind,identity in entries:
            existing=db.scalar(select(model).filter_by(**identity,requested_by_id=user.id,wanted_quality=body.wanted_quality))
            if existing:created.append(str(existing.id));continue
            row=model(id=uuid4(),requested_by_id=user.id,wanted_quality=body.wanted_quality,min_quality=body.min_quality,**identity)
            apply_request_policy(db,row,kind);db.add(row);db.flush();created.append(str(row.id))
        db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'This title has already been requested. Refresh your requests.') from None
    except Exception:db.rollback();raise
    # Request lifecycle notifications are emitted by the durable observer for every submission route.
    return {'request_ids':created,'authorized':bool(user.is_superuser or user.auto_approve_requests),'used':usage_count(db,user.id)}


def related_files(db,kind,media,season=None,episode=None):
    if kind=='movie':return list(db.scalars(select(MovieFile).where(MovieFile.movie_id==media.id)))
    rows=list(db.scalars(select(SeasonFile).where(SeasonFile.season_id==season.id)))
    if episode is None:return rows
    from media_manager.library import episode_numbers
    return [r for r in rows if (not r.episode_numbers and (r.torrent_id is None or not episode_numbers([db.get(Torrent,r.torrent_id).title],season.number))) or episode.number in (r.episode_numbers or episode_numbers([db.get(Torrent,r.torrent_id).title],season.number))]

@router.get('/center')
def center(db:DbSessionDependency,tv:tv_service_dep,movies:movie_service_dep,user:Annotated[User,Depends(current_active_user)],kind:Literal['all','movie','tv']='all'):
    from media_manager.movies.schemas import Movie as MovieDTO
    from media_manager.library_availability import season_presence
    rows=[];presence={};jobs={}
    def add(request,media,typ,season=None,episode=None):
        if not user.is_superuser and request.requested_by_id!=user.id:return
        if kind!='all' and kind!=('movie' if typ=='movie' else 'tv'):return
        files=related_files(db,'movie' if typ=='movie' else 'tv',media,season,episode)
        associated=[db.get(Torrent,f.torrent_id) for f in files if f.torrent_id]
        associated=[t for t in associated if t is not None];jobs.update({str(t.id):t for t in associated})
        if typ=='movie':done=movies.is_movie_downloaded(MovieDTO.model_validate(media))
        else:
            if season.id not in presence:
                dto=tv.tv_repository.get_show_by_id(media.id);sd=next(s for s in dto.seasons if s.id==season.id);presence[season.id]=season_presence(tv,dto,sd)
            if episode:done=episode.number in presence[season.id]
            else:
                required={e.number for e in db.scalars(select(Episode).where(Episode.season_id==season.id)) if e.air_date is None or e.air_date<=datetime.now(ZoneInfo('Europe/Berlin')).date()}
                done=bool(required) and required<=presence[season.id]
        active=[t for t in associated if not t.imported]
        from media_manager.media_features_models import RequestState
        delivery=db.get(RequestState,(typ,request.id))
        rejected=bool(delivery and delivery.rejected and not request.authorized)
        emby_available=delivery.emby_available if delivery else None
        state='rejected' if rejected else 'finished' if done and (emby_available is True or not MediaManagerConfig().emby.enabled) else 'waiting_emby' if done else 'running' if active else 'approved' if request.authorized else 'pending'
        rows.append({'id':str(request.id),'kind':typ,'media_id':str(media.id),'name':media.name,'year':media.year,'season_number':season.number if season else None,'episode_number':episode.number if episode else None,'authorized':request.authorized,'requested_by_id':str(request.requested_by_id) if request.requested_by_id else None,'requested_by':db.get(User,request.requested_by_id).email if user.is_superuser and request.requested_by_id else None,'status':state,'rejection_reason':delivery.reason if rejected else None,'emby_available':emby_available,'job_ids':[str(t.id) for t in active],'percent':100 if done else None})
    q=select(MovieRequest,Movie).join(Movie,MovieRequest.movie_id==Movie.id)
    if not user.is_superuser:q=q.where(MovieRequest.requested_by_id==user.id)
    for request,media in db.execute(q):add(request,media,'movie')
    q=select(SeasonRequest,Season,Show).join(Season,SeasonRequest.season_id==Season.id).join(Show,Season.show_id==Show.id)
    if not user.is_superuser:q=q.where(SeasonRequest.requested_by_id==user.id)
    for request,season,show in db.execute(q):add(request,show,'season',season)
    q=select(EpisodeRequest,Episode,Season,Show).join(Episode,EpisodeRequest.episode_id==Episode.id).join(Season,Episode.season_id==Season.id).join(Show,Season.show_id==Show.id)
    if not user.is_superuser:q=q.where(EpisodeRequest.requested_by_id==user.id)
    for request,episode,season,show in db.execute(q):add(request,show,'episode',season,episode)
    if user.is_superuser:jobs.update({str(t.id):t for t in db.scalars(select(Torrent).where(Torrent.imported==False))})
    progress=tv.torrent_service.download_manager.get_progress([t for t in jobs.values() if not t.imported])
    for row in rows:
        row['progress']=[progress[j] for j in row['job_ids'] if j in progress]
        values=[p['percent'] for p in row['progress'] if p.get('percent') is not None]
        if values:row['percent']=min(values)
    counts={s:sum(r['status']==s for r in rows) for s in ['pending','approved','running','waiting_emby','finished','rejected']}
    quota={'limit':None if user.is_superuser else user.monthly_request_limit,'used':usage_count(db,user.id),'resets_at':month_bounds()[1]}
    return {'requests':rows,'counts':counts,'quota':quota,'is_admin':user.is_superuser,'downloads':[dict(v,id=k,title=jobs[k].title) for k,v in progress.items()] if user.is_superuser else []}

class Approval(BaseModel):
    authorized:bool
    reason:str|None=Field(default=None,max_length=2000)
@router.put('/center/{kind}/{request_id}',dependencies=[Depends(current_superuser)])
def approve(kind:Literal['movie','season','episode'],request_id:UUID,body:Approval,db:DbSessionDependency,user:Annotated[User,Depends(current_superuser)]):
    model={'movie':MovieRequest,'season':SeasonRequest,'episode':EpisodeRequest}[kind];row=db.get(model,request_id)
    if not row:raise HTTPException(404,'Request not found.')
    from media_manager.media_features_models import RequestState
    from media_manager.account_notifications import enqueue,describe,now
    from media_manager.tv.models import Season,Episode
    if kind=='movie':media=db.get(Movie,row.movie_id);season=episode=None
    elif kind=='season':season=db.get(Season,row.season_id);media=db.get(Show,season.show_id);episode=None
    else:episode=db.get(Episode,row.episode_id);season=db.get(Season,episode.season_id);media=db.get(Show,season.show_id)
    state=db.get(RequestState,(kind,row.id))
    if state is None:state=RequestState(kind=kind,request_id=row.id,state='pending',rejected=False,reason=None,emby_available=None,first_seen=now());db.add(state)
    changed=(row.authorized!=body.authorized) or (not body.authorized and not state.rejected)
    row.authorized=body.authorized;row.authorized_by_id=user.id if body.authorized else None
    state.rejected=not body.authorized;state.reason=(body.reason or '').strip() or None;state.state='approved' if body.authorized else 'rejected'
    recipient=db.get(User,row.requested_by_id) if row.requested_by_id else None
    if changed and recipient:
        category='request_approved' if body.authorized else 'request_rejected';details=describe(db,media,row,season,episode);details['reason']=state.reason or ''
        enqueue(db,f'{kind}:{row.id}:'+('approved' if body.authorized else 'rejected'),recipient,category,details)
    db.commit();return {'saved':True}
