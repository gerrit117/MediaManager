"""Persistent library catalogue jobs. Existing media is read-only unless explicitly reorganized."""
import fcntl,json,re,hashlib,logging
from datetime import datetime,timezone,timedelta
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from uuid import uuid5,NAMESPACE_URL
import requests
from pydantic import Field,model_validator
from pydantic_settings import BaseSettings
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,BackgroundTasks,HTTPException,Request
from typing import Literal
from media_manager.auth.users import current_superuser,current_active_user
from media_manager.library_scan_config import LibraryScanConfig
from media_manager.configuration import atomic_json,config_file

log=logging.getLogger(__name__)

def state_path():return config_file().parent/'library-scan-status.json'
def now():return datetime.now(timezone.utc).isoformat()
def lock_scan():
    file=(config_file().parent/'library-scan.lock').open('a')
    try:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:file.close();raise HTTPException(409,'A library scan is already running.') from None
    return file

def read_status():
    try:data=json.loads(state_path().read_text())
    except (FileNotFoundError,ValueError):return {'status':'idle','processed':0,'total':0,'imported':0,'skipped':0,'review':[],'errors':[]}
    if data.get('status')=='running':
        try:probe=lock_scan()
        except HTTPException:return data
        else:
            try:
                # The worker can finish between the initial read and acquiring this lease.
                # Re-read while holding it; never overwrite a completed scan or a newer job.
                try:data=json.loads(state_path().read_text())
                except (FileNotFoundError,ValueError):return {'status':'idle','processed':0,'total':0,'imported':0,'skipped':0,'review':[],'errors':[]}
                if data.get('status')=='running':
                    data['status']='interrupted';atomic_json(state_path(),data)
            finally:probe.close()
    return data

def source_json(cfg,source,endpoint,params=None):
    response=requests.get(getattr(cfg,source+'_url').rstrip('/')+'/api/v3/'+endpoint,
        headers={'X-Api-Key':getattr(cfg,source+'_api_key')},params=params,timeout=25,allow_redirects=False)
    if response.status_code!=200:raise ValueError(source+' metadata request failed (HTTP '+str(response.status_code)+')')
    data=response.json()
    if not isinstance(data,list):raise ValueError(source+' returned invalid metadata')
    return data

def source_index(cfg,source):
    if not getattr(cfg,source+'_url') or not getattr(cfg,source+'_api_key'):return {}
    result={};root=PurePosixPath(getattr(cfg,source+'_root'))
    for entry in source_json(cfg,source,'movie' if source=='radarr' else 'series'):
        path=PurePosixPath(entry.get('path',''))
        if '..' in path.parts or not path.is_relative_to(root) or path.parent!=root:continue
        if path.name in result:result[path.name]=None # Ambiguous mappings must be reviewed.
        else:result[path.name]=entry
    return result

def read_nfo(folder,kind):
    paths=([folder/'tvshow.nfo'] if kind=='tv' else sorted(folder.glob('*.nfo')))
    for path in paths:
        if not path.is_file() or path.is_symlink() or path.stat().st_size>2_000_000:continue
        raw=path.read_bytes()
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():continue
        try:node=ET.fromstring(raw)
        except ET.ParseError:continue
        if node.tag!=('tvshow' if kind=='tv' else 'movie'):continue
        ids={e.attrib.get('type','').lower():e.text.strip() for e in node.findall('uniqueid') if e.text}
        for key in ['tmdb','tvdb','imdb']:
            value=node.findtext(key+'id')
            if value:ids[key]=value.strip()
        provider='tvdb' if kind=='tv' and ids.get('tvdb') else 'tmdb'
        value=ids.get(provider)
        if not value or not str(value).isdigit():continue
        return {'title':node.findtext('title') or folder.name,'year':int(node.findtext('year')) if (node.findtext('year') or '').isdigit() else None,
            'overview':node.findtext('plot') or '', 'provider':provider,'external_id':int(value),'imdbId':ids.get('imdb')}
    return None

def stable_id(provider,kind,external):return uuid5(NAMESPACE_URL,f'mediamanager:{provider}:{kind}:{external}')
def parse_date(value):
    from datetime import date
    try:return date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError):return None

def identity(entry,kind):
    if kind=='tv' and int(entry.get('tvdbId') or 0)>0:return 'tvdb',int(entry['tvdbId'])
    return 'tmdb',int(entry.get('tmdbId') or 0)

def build_show(entry,episodes):
    from media_manager.tv.schemas import Show,Season,Episode
    provider,external=identity(entry,'tv');seasons=[]
    for number in sorted({e['seasonNumber'] for e in episodes if e.get('episodeNumber',0)>0}):
        items=[e for e in episodes if e['seasonNumber']==number and e.get('episodeNumber',0)>0]
        seasons.append(Season(id=stable_id(provider,'season',f'{external}:{number}'),number=number,external_id=0,name='Season '+str(number),overview='',
            episodes=[Episode(id=stable_id(provider,'episode',f'{external}:{number}:{e["episodeNumber"]}'),number=e['episodeNumber'],external_id=(e.get('tvdbId') or 0) if provider=='tvdb' else 0,title=e.get('title') or '',air_date=parse_date(e.get('airDate'))) for e in items]))
    return Show(id=stable_id(provider,'show',external),external_id=external,metadata_provider=provider,name=entry['title'],overview=entry.get('overview') or '',year=entry.get('year'),imdb_id=entry.get('imdbId'),ended=bool(entry.get('ended')),library='Default',seasons=seasons)

def save_poster(folder,model,cfg,source=None,entry=None):
    from media_manager.config import MediaManagerConfig
    from PIL import Image
    from io import BytesIO
    target=MediaManagerConfig().misc.image_directory/(str(model.id)+'.jpeg')
    if target.exists():return
    try:
        files=[folder/'poster.jpg',folder/'folder.jpg',*sorted(folder.glob('*-poster.jpg'))]
        file=next((p for p in files if p.is_file() and not p.is_symlink() and p.stat().st_size<8_000_000),None)
        raw=file.read_bytes() if file else None
        if raw is None and source and entry:
            image=next((i for i in entry.get('images',[]) if i.get('coverType')=='poster' and i.get('url','').startswith('/MediaCover/')),None)
            if image:
                response=requests.get(getattr(cfg,source+'_url').rstrip('/')+image['url'],headers={'X-Api-Key':getattr(cfg,source+'_api_key')},timeout=10,allow_redirects=False)
                if response.status_code==200 and len(response.content)<8_000_000:raw=response.content
        if raw:
            target.parent.mkdir(parents=True,exist_ok=True)
            with Image.open(BytesIO(raw)) as image:image.convert('RGB').save(target,format='JPEG')
    except Exception:log.info('Poster could not be copied for catalogue ID %s',model.id)

def known_directories(db,root,kind):
    from media_manager.movies.models import MovieFile
    from media_manager.tv.models import SeasonFile,Season
    if kind=='movies':rows=db.execute(select(MovieFile.movie_id,MovieFile.source_files)).all()
    else:rows=db.execute(select(Season.show_id,SeasonFile.source_files).join(Season,SeasonFile.season_id==Season.id)).all()
    mapping={}
    for identity,files in rows:
        for file in files or []:
            try:parts=Path(file).relative_to(root).parts
            except ValueError:continue
            if len(parts)<2:continue
            name=parts[0]
            if name in mapping and mapping[name]!=identity:mapping[name]=None
            else:mapping[name]=identity
    return mapping

def run_scan(lease,mode='catalogue'):
    from media_manager.config import MediaManagerConfig
    from media_manager.database import init_engine
    from media_manager.movies.repository import MovieRepository
    from media_manager.tv.repository import TvRepository
    from media_manager.movies.service import MovieService
    from media_manager.tv.service import TvService
    from media_manager.movies.schemas import Movie
    from media_manager.exceptions import NotFoundError
    from media_manager.library import video_files,episode_numbers
    import media_manager.auth.request_policy
    import media_manager.torrent.models
    state={'status':'running','started_at':now(),'mode':mode,'processed':0,'total':0,'imported':0,'skipped':0,'review':[],'errors':[],'current':''}
    def persist():atomic_json(state_path(),state)
    persist()
    try:
        config=MediaManagerConfig();cfg=config.misc.library_scan
        sources={}
        for name in ['radarr','sonarr']:
            try:sources[name]=source_index(cfg,name)
            except Exception as error:
                sources[name]={};state['errors'].append({'source':name,'message':'Metadata source is unavailable. Check URL and API key.'});persist()
        from media_manager.torrent.utils import get_importable_media_directories
        directories=[(kind,p) for kind,root in [('movies',config.misc.movie_directory),('tv',config.misc.tv_directory)] for p in sorted(get_importable_media_directories(root)) if not p.is_symlink()]
        state['total']=len(directories);persist()
        with Session(init_engine(config.database)) as db:
            movie_repo=MovieRepository(db);tv_repo=TvRepository(db)
            known_movies=known_directories(db,config.misc.movie_directory,'movies');known_shows=known_directories(db,config.misc.tv_directory,'tv')
            ms=MovieService.__new__(MovieService);ms.movie_repository=movie_repo
            ts=TvService.__new__(TvService);ts.tv_repository=tv_repo
            for kind,folder in directories:
                state['current']=folder.name
                try:
                    files=video_files(folder)
                    if not files:state['skipped']+=1;continue
                    from media_manager.torrent.utils import extract_external_id_from_string
                    md,external=extract_external_id_from_string(folder.name)
                    if md and external:
                        try:
                            if kind=='movies':known_movies.setdefault(folder.name,movie_repo.get_movie_by_external_id(external,md).id)
                            else:known_shows.setdefault(folder.name,tv_repo.get_show_by_external_id(external,md).id)
                        except NotFoundError:pass
                    source='radarr' if kind=='movies' else 'sonarr';entry=sources[source].get(folder.name)
                    nfo=read_nfo(folder,kind)
                    recorded_id=(known_movies if kind=='movies' else known_shows).get(folder.name)
                    if recorded_id:
                        recorded=(movie_repo.get_movie_by_id(recorded_id) if kind=='movies' else tv_repo.get_show_by_id(recorded_id))
                        candidate=identity(entry,kind) if entry else ((nfo['provider'],nfo['external_id']) if nfo else None)
                        if candidate and candidate!=(recorded.metadata_provider,recorded.external_id):
                            entry=None;nfo=None # A saved detail-page correction must survive future scans.
                    if entry:
                        provider,external=identity(entry,kind)
                        if external<=0:entry=None
                        elif nfo and nfo['provider']==provider and nfo['external_id']!=external:
                            state['review'].append({'kind':kind,'directory':str(folder),'reason':'Metadata IDs disagree.'});continue
                    if kind=='movies':
                        if not entry and not nfo and not known_movies.get(folder.name):state['review'].append({'kind':kind,'directory':str(folder),'reason':'No trusted metadata ID. Match this directory manually.'});continue
                        if not entry and not nfo:
                            model=movie_repo.get_movie_by_id(known_movies[folder.name]);provider=model.metadata_provider;external=model.external_id
                        else:
                            if entry:provider='tmdb';external=int(entry['tmdbId'])
                            else:provider=nfo['provider'];external=nfo['external_id']
                            try:model=movie_repo.get_movie_by_external_id(external,provider)
                            except NotFoundError:model=None
                        if model is None:
                            data=entry or nfo
                            model=movie_repo.save_movie(Movie(id=stable_id(provider,'movie',external),external_id=external,metadata_provider=provider,name=data['title'],year=data.get('year'),overview=data.get('overview') or '',imdb_id=data.get('imdbId'),library='Default'))
                        ok=ms.catalogue_existing_movie(model,folder) if mode=='catalogue' else ms.import_existing_movie(model,folder)
                    else:
                        if entry:
                            provider,external=identity(entry,'tv')
                            try:model=tv_repo.get_show_by_external_id(external,provider)
                            except NotFoundError:model=None
                            if model is None and entry.get('tmdbId'):
                                try:model=tv_repo.get_show_by_external_id(int(entry['tmdbId']),'tmdb')
                                except NotFoundError:pass
                            episodes=source_json(cfg,'sonarr','episode',{'seriesId':entry['id']})
                            fresh=build_show(entry,episodes)
                            if not any(episode_numbers(files,s.number) for s in fresh.seasons):
                                state['review'].append({'kind':kind,'directory':str(folder),'reason':'No recognizable video/episode files.'});continue
                            if model is None:model=tv_repo.save_show(fresh)
                            else:
                                # Preserve provider identities, IDs, libraries and monitoring preferences.
                                fresh.id=model.id;fresh.external_id=model.external_id;fresh.metadata_provider=model.metadata_provider
                                # A library scan refreshes file/episode coverage, not manually edited display details.
                                fresh.name=model.name;fresh.year=model.year;fresh.overview=model.overview
                                if model.metadata_provider=='tmdb':
                                    for season in fresh.seasons:
                                        known=next((s for s in model.seasons if s.number==season.number),None)
                                        season.external_id=known.external_id if known else 0
                                        for episode in season.episodes:
                                            known_episode=next((e for e in known.episodes if e.number==episode.number),None) if known else None
                                            episode.external_id=known_episode.external_id if known_episode else 0
                                from types import SimpleNamespace
                                provider=SimpleNamespace(name=model.metadata_provider,get_show_metadata=lambda **kwargs:fresh,download_show_poster_image=lambda **kwargs:False)
                                model=ts.update_show_metadata(model,provider);db.commit()
                        elif nfo:
                            from media_manager.metadataProvider.dependencies import get_metadata_provider
                            provider=nfo['provider'];external=nfo['external_id']
                            try:model=tv_repo.get_show_by_external_id(external,provider)
                            except NotFoundError:model=None
                            if model is None:
                                api=get_metadata_provider(provider);model=api.get_show_metadata(external)
                                if model is not None:model=tv_repo.save_show(model)
                        elif known_shows.get(folder.name):model=tv_repo.get_show_by_id(known_shows[folder.name])
                        else:state['review'].append({'kind':kind,'directory':str(folder),'reason':'No trusted metadata ID. Match this directory manually.'});continue
                        if model is None:state['review'].append({'kind':kind,'directory':str(folder),'reason':'Metadata could not be loaded.'});continue
                        ok=ts.catalogue_existing_tv_show(model,folder) if mode=='catalogue' else (ts.import_existing_tv_show(model,folder) is None)
                    if ok:
                        state['imported']+=1;save_poster(folder,model,cfg,source if entry else None,entry)
                    else:state['review'].append({'kind':kind,'directory':str(folder),'reason':'No recognizable video/episode files.'})
                except Exception as error:
                    db.rollback();state['errors'].append({'kind':kind,'directory':str(folder),'message':'Import failed. Check the server logs for this directory.'});log.exception('Catalogue import failed for %s',folder)
                finally:state['processed']+=1;persist()
        state['status']='completed';state['finished_at']=now();state['current']='';persist()
    except Exception as error:
        state['status']='failed';state['finished_at']=now();state['errors'].append({'message':'Library scan failed. Check paths, permissions and server logs.'});persist();log.exception('Library scan failed')
    finally:lease.close()

def automatic_scan():
    from media_manager.config import MediaManagerConfig
    cfg=MediaManagerConfig().misc.library_scan
    if not cfg.automatic:return
    status=read_status()
    last=status.get('finished_at') or status.get('started_at')
    if last and datetime.now(timezone.utc)-datetime.fromisoformat(last)<timedelta(hours=cfg.interval_hours):return
    try:lease=lock_scan()
    except HTTPException:return
    run_scan(lease,'catalogue')

router=APIRouter()
@router.get('/summary',dependencies=[Depends(current_active_user)])
def summary():
    from media_manager.config import MediaManagerConfig
    from media_manager.database import init_engine
    from media_manager.movies.models import Movie
    from media_manager.tv.models import Show
    with Session(init_engine(MediaManagerConfig().database)) as db:
        return {'movies':db.scalar(select(func.count(Movie.id))),'shows':db.scalar(select(func.count(Show.id))),
                'paths':{'movies':str(MediaManagerConfig().misc.movie_directory),'tv':str(MediaManagerConfig().misc.tv_directory)}}

@router.get('/scan',dependencies=[Depends(current_superuser)])
def scan_status():return read_status()

@router.post('/scan',status_code=202,dependencies=[Depends(current_superuser)])
def start_scan(tasks:BackgroundTasks,request:Request,mode:Literal['catalogue','reorganize']='catalogue',confirm_reorganize:bool=False):
    origin=request.headers.get('origin')
    if origin and urlsplit(origin).netloc!=request.headers.get('host'):raise HTTPException(403,'Cross-origin scan requests are not allowed.')
    if mode=='reorganize' and not confirm_reorganize:raise HTTPException(400,'Reorganization requires explicit confirmation.')
    lease=lock_scan()
    atomic_json(state_path(),{'status':'running','started_at':now(),'processed':0,'total':0,'imported':0,'skipped':0,'review':[],'errors':[],'mode':mode})
    tasks.add_task(run_scan,lease,mode)
    return {'started':True,'mode':mode}
