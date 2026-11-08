"""Individual episode requests use the same monthly quotas and approval policy as seasons."""
from uuid import UUID,uuid4
from typing import Annotated
from datetime import datetime,timezone
import logging
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from media_manager.database import DbSessionDependency
from media_manager.auth.users import current_active_user,current_superuser
from media_manager.auth.db import User
from media_manager.auth.request_policy import apply_request_policy
from media_manager.library_models import EpisodeRequest
from media_manager.tv.models import Episode,Season,Show,EpisodeDownload
from media_manager.tv.schemas import SeasonRequestBase
from media_manager.tv.dependencies import tv_service_dep
from media_manager.library_availability import season_presence
from media_manager.tv.monitor import claimed_episodes

log=logging.getLogger(__name__)
router=APIRouter()
class EpisodeRequestCreate(SeasonRequestBase):
    episode_id: UUID
class Approval(BaseModel):
    authorized: bool

def context(service,episode_id):
    db=service.tv_repository.db;episode=db.get(Episode,episode_id)
    if episode is None:raise HTTPException(404,'Episode not found.')
    season=db.get(Season,episode.season_id);show=service.tv_repository.get_show_by_id(season.show_id)
    dto=next(s for s in show.seasons if s.id==season.id)
    return show,dto,next(e for e in dto.episodes if e.id==episode_id)


def search_episode(service,show,season,episode):
    results=service.get_all_available_torrents_for_a_season(season.number,show.id,search_query_override=f'{show.name} S{season.number:02d}E{episode.number:02d}')
    from media_manager.library import episode_numbers
    return [r for r in results if r.season==[season.number] and episode_numbers([r.title],season.number)=={episode.number}]


def submit_episode(service,show,season,episode,result_id):
    db=service.tv_repository.db
    if episode.number in season_presence(service,show,season):raise HTTPException(409,'This episode already exists in the library.')
    if episode.number in claimed_episodes(service,season):raise HTTPException(409,'An existing download already covers this episode. Check Downloads before retrying.')
    from media_manager.library import episode_numbers
    result=service.indexer_service.get_result(result_id)
    if result.season!=[season.number] or episode_numbers([result.title],season.number)!={episode.number}:raise HTTPException(409,'The release does not match this episode.')
    from media_manager.release_policy import assert_allowed
    assert_allowed(result)
    inserted=db.execute(insert(EpisodeDownload).values(episode_id=episode.id,status='submitting',release_title=result.title,checked_at=datetime.now(timezone.utc)).on_conflict_do_nothing(index_elements=['episode_id']).returning(EpisodeDownload.episode_id)).scalar_one_or_none()
    if inserted is None:
        job=db.scalars(select(EpisodeDownload).where(EpisodeDownload.episode_id==episode.id).with_for_update()).one()
        if job.status!='imported':db.rollback();raise HTTPException(409,'An earlier submission needs review before retrying this episode.')
        job.status='submitting';job.release_title=result.title;job.error=None
    db.commit()
    try:
        torrent=service.download_torrent(result_id,show.id)
        job=db.get(EpisodeDownload,episode.id);job.torrent_id=torrent.id;job.status='submitted';db.commit();return torrent
    except HTTPException:
        db.rollback();job=db.get(EpisodeDownload,episode.id)
        job.status='uncertain';job.error='Submission could not be confirmed; inspect Downloads before retrying.';db.commit()
        raise
    except Exception:
        db.rollback();job=db.get(EpisodeDownload,episode.id);job.status='uncertain';job.error='Submission could not be confirmed; inspect Downloads before retrying.';db.commit()
        raise HTTPException(502,'Submission could not be confirmed. Check Downloads before retrying.') from None


@router.get('/episodes/requests')
def list_requests(db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    query=select(EpisodeRequest,Episode,Season,Show).join(Episode,EpisodeRequest.episode_id==Episode.id).join(Season,Episode.season_id==Season.id).join(Show,Season.show_id==Show.id)
    if not user.is_superuser:query=query.where(EpisodeRequest.requested_by_id==user.id)
    rows=[]
    for request,episode,season,show in db.execute(query):
        job=db.get(EpisodeDownload,episode.id)
        rows.append({'id':str(request.id),'episode_id':str(episode.id),'show_id':str(show.id),'show_name':show.name,'season_number':season.number,'episode_number':episode.number,'episode_title':episode.title,'authorized':request.authorized,'requested_by_id':str(request.requested_by_id) if request.requested_by_id else None,'status':job.status if job else 'approved' if request.authorized else 'pending','min_quality':request.min_quality.value,'wanted_quality':request.wanted_quality.value})
    return rows


@router.post('/episodes/requests',status_code=201)
def request_episode(body:EpisodeRequestCreate,service:tv_service_dep,user:Annotated[User,Depends(current_active_user)],tasks:BackgroundTasks):
    show,season,episode=context(service,body.episode_id);db=service.tv_repository.db
    if episode.number in season_presence(service,show,season):raise HTTPException(409,'This episode already exists in the library.')
    if episode.number in claimed_episodes(service,season):raise HTTPException(409,'An existing download already covers this episode. Check Downloads before retrying.')
    row=EpisodeRequest(id=uuid4(),episode_id=episode.id,requested_by_id=user.id,min_quality=body.min_quality,wanted_quality=body.wanted_quality)
    try:apply_request_policy(db,row,'episodes');db.add(row);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'This episode has already been requested at this quality.') from None
    from media_manager.auth.mail import notify_admins
    tasks.add_task(notify_admins,'New episode request',str(user.email)+': '+show.name+' S'+str(season.number)+'E'+str(episode.number))
    return {'id':str(row.id),'authorized':row.authorized}


@router.put('/episodes/requests/{request_id}',dependencies=[Depends(current_superuser)])
def approve(request_id:UUID,body:Approval,db:DbSessionDependency,user:Annotated[User,Depends(current_superuser)]):
    row=db.get(EpisodeRequest,request_id)
    if row is None:raise HTTPException(404,'Request not found.')
    row.authorized=body.authorized;row.authorized_by_id=user.id if body.authorized else None;db.commit();return {'saved':True}


@router.delete('/episodes/requests/{request_id}',status_code=204)
def delete_request(request_id:UUID,db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    row=db.get(EpisodeRequest,request_id)
    if row is None:raise HTTPException(404,'Request not found.')
    if not user.is_superuser and row.requested_by_id!=user.id:raise HTTPException(403,'Not allowed to delete this request.')
    db.delete(row);db.commit()


@router.get('/episodes/{episode_id}/releases',dependencies=[Depends(current_superuser)])
def releases(episode_id:UUID,service:tv_service_dep):
    show,season,episode=context(service,episode_id);return search_episode(service,show,season,episode)


@router.post('/episodes/{episode_id}/download',dependencies=[Depends(current_superuser)])
def download(episode_id:UUID,result_id:UUID,service:tv_service_dep):
    show,season,episode=context(service,episode_id);return submit_episode(service,show,season,episode,result_id)


def process_approved(service):
    db=service.tv_repository.db
    from media_manager.release_policy import allowed_results
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo('Europe/Berlin')).date()
    for request in list(db.scalars(select(EpisodeRequest).where(EpisodeRequest.authorized==True))):
        try:
            show,season,episode=context(service,request.episode_id)
            if episode.air_date and episode.air_date>today:continue
            if episode.number in season_presence(service,show,season) or episode.number in claimed_episodes(service,season):continue
            job=db.get(EpisodeDownload,episode.id)
            if job and job.status!='imported':continue
            results=allowed_results([r for r in search_episode(service,show,season,episode) if request.wanted_quality.value<=r.quality.value<=request.min_quality.value],available_only=True)
            if results:submit_episode(service,show,season,episode,results[0].id)
        except Exception:
            db.rollback();log.exception('Episode request could not be processed: %s',request.id)


def run_approved():
    from media_manager.database import get_session
    from media_manager.tv.service import TvService
    from media_manager.tv.repository import TvRepository
    from media_manager.torrent.repository import TorrentRepository
    from media_manager.torrent.service import TorrentService
    from media_manager.indexer.repository import IndexerRepository
    from media_manager.indexer.service import IndexerService
    from media_manager.notification.repository import NotificationRepository
    from media_manager.notification.service import NotificationService
    with next(get_session()) as db:
        service=TvService(TvRepository(db),TorrentService(TorrentRepository(db)),IndexerService(IndexerRepository(db)),NotificationService(NotificationRepository(db)))
        process_approved(service)
