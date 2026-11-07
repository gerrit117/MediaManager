"""Resolve series using provider IDs and IMDb, never fuzzy title matches."""
import re,hashlib
from contextlib import contextmanager
from sqlalchemy import select,func,text
from fastapi import HTTPException
from media_manager.tv.models import Show,Season,SeasonFile,SeasonRequest,Episode,EpisodeDownload
from media_manager.library_models import ShowExternalId,EpisodeRequest


def identifiers(provider,external_id,imdb=None):
    ids={provider:str(external_id)}
    if imdb and re.fullmatch(r'tt\d+',imdb):ids['imdb']=imdb
    return ids


def resolve(db,ids):
    found=set()
    for provider,external in ids.items():
        alias=db.get(ShowExternalId,(provider,str(external)))
        if alias:found.add(alias.show_id)
        if provider=='imdb':found.update(db.scalars(select(Show.id).where(Show.imdb_id==external)).all())
        elif provider in ['tmdb','tvdb']:found.update(db.scalars(select(Show.id).where(Show.metadata_provider==provider,Show.external_id==int(external))).all())
    if len(found)>1:raise HTTPException(409,'Multiple series share these provider IDs. Review the duplicate records before adding this series.')
    return db.get(Show,next(iter(found))) if found else None


def register(db,show_id,ids):
    for provider,value in ids.items():
        value=str(value)
        if provider not in ['imdb','tvdb','tmdb'] or not value:continue
        if provider=='imdb' and not re.fullmatch(r'tt\d+',value):continue
        if provider!='imdb' and (not value.isdigit() or int(value)<=0):continue
        row=db.get(ShowExternalId,(provider,value))
        if row and row.show_id!=show_id:raise HTTPException(409,'This provider ID already belongs to another series.')
        if row is None:db.add(ShowExternalId(provider=provider,external_id=value,show_id=show_id));db.flush()


@contextmanager
def identity_lock(db,ids):
    if db.get_bind().dialect.name!='postgresql':yield;return
    key=ids.get('imdb') or '|'.join(f'{k}:{v}' for k,v in sorted(ids.items()))
    number=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],'big')&((1<<63)-1)
    with db.get_bind().connect() as connection:
        connection.execute(text('SELECT pg_advisory_lock(:key)'),{'key':number})
        try:yield
        finally:connection.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':number})


def merge_empty_duplicate(db,keep,remove):
    """Only remove metadata-only duplicates proven by IMDb. Never merge media histories blindly."""
    if keep.id==remove.id or not keep.imdb_id or keep.imdb_id!=remove.imdb_id:raise HTTPException(409,'The series identities are not an exact match.')
    seasons=list(db.scalars(select(Season.id).where(Season.show_id==remove.id)))
    episodes=list(db.scalars(select(Episode.id).where(Episode.season_id.in_(seasons))))
    counts=[db.scalar(select(func.count()).select_from(cls).where(column.in_(values))) for cls,column,values in [(SeasonFile,SeasonFile.season_id,seasons),(SeasonRequest,SeasonRequest.season_id,seasons),(EpisodeDownload,EpisodeDownload.episode_id,episodes),(EpisodeRequest,EpisodeRequest.episode_id,episodes)]]
    if any(counts):raise HTTPException(409,'The duplicate has files, requests or downloads. Manual review is required; nothing was deleted.')
    if remove.library not in ['', 'Default',keep.library]:raise HTTPException(409,'The duplicate uses a different target library. Review it before merging.')
    if remove.continuous_download:
        keep.continuous_download=True
        if remove.monitor_from:keep.monitor_from=min(x for x in [keep.monitor_from,remove.monitor_from] if x is not None)
    aliases=list(db.scalars(select(ShowExternalId).where(ShowExternalId.show_id==remove.id)))
    ids=identifiers(remove.metadata_provider,remove.external_id,remove.imdb_id)
    for alias in aliases:ids[alias.provider]=alias.external_id;db.delete(alias)
    db.flush();removed_id=remove.id;db.delete(remove);db.flush()
    register(db,keep.id,ids);register(db,keep.id,identifiers(keep.metadata_provider,keep.external_id,keep.imdb_id))
    return {'kept':str(keep.id),'removed':str(removed_id),'files_changed':False}
