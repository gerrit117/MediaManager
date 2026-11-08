from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from media_manager.auth.users import current_active_user,current_superuser
from media_manager.database import DbSessionDependency
from media_manager.media_features_models import ReleaseLock,Replacement
from media_manager.release_control import locked
router=APIRouter()
def entity(db,kind,media_id):
    from media_manager.movies.models import Movie
    from media_manager.tv.models import Show,Season,Episode
    row=db.get({'movie':Movie,'show':Show,'season':Season,'episode':Episode}[kind],media_id)
    if row is None:raise HTTPException(404,'Media not found.')
    return row
@router.get('/protection/{kind}/{media_id}',dependencies=[Depends(current_active_user)])
def get_lock(kind:Literal['movie','show','season','episode'],media_id:UUID,db:DbSessionDependency):
    entity(db,kind,media_id)
    return {'locked':locked(db,kind,media_id),'own_lock':db.get(ReleaseLock,(kind,media_id)) is not None}
class LockBody(BaseModel):locked:bool
@router.put('/protection/{kind}/{media_id}',dependencies=[Depends(current_superuser)])
def set_lock(kind:Literal['movie','show','season','episode'],media_id:UUID,body:LockBody,db:DbSessionDependency):
    entity(db,kind,media_id);row=db.get(ReleaseLock,(kind,media_id))
    if body.locked and row is None:db.add(ReleaseLock(kind=kind,media_id=media_id))
    elif not body.locked and row is not None:db.delete(row)
    db.commit();return get_lock(kind,media_id,db)
@router.get('/replacements',dependencies=[Depends(current_superuser)])
def replacements(db:DbSessionDependency):
    return [{'job_id':r.job_id,'kind':r.kind,'media_id':r.media_id,'status':r.status,'archived_files':r.manifest.get('archived_files',[])} for r in db.scalars(select(Replacement))]
@router.post('/emby/test',dependencies=[Depends(current_superuser)])
def test_emby():
    from media_manager.emby import EmbyClient
    client=EmbyClient()
    if not client.config.url or not client.config.api_key:raise HTTPException(400,'Configure the Emby server and API key first.')
    try:data=client.get('System/Info')
    except Exception:raise HTTPException(502,'Emby connection failed. Check address and API key.') from None
    return {'connected':True,'server_name':data.get('ServerName'),'version':data.get('Version')}

@router.get('/emby/matches',dependencies=[Depends(current_superuser)])
def emby_matches(db:DbSessionDependency):
    from media_manager.emby_matching import summary
    return summary(db)
@router.post('/emby/matches',dependencies=[Depends(current_superuser)])
def match_emby(db:DbSessionDependency):
    from media_manager.emby_matching import scan
    from media_manager.config import MediaManagerConfig
    if not MediaManagerConfig().emby.enabled:raise HTTPException(400,'Enable the Emby connection first.')
    try:return scan(db)
    except Exception:db.rollback();raise HTTPException(502,'Emby library matching failed; existing matches were retained.') from None
