"""Cached collection membership, fetched from documented TMDB/Radarr APIs."""
from datetime import datetime,timezone,date
from pathlib import Path
import logging,threading
import requests
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from media_manager.auth.users import current_active_user,current_superuser
from media_manager.database import DbSessionDependency
from media_manager.library_models import MovieCollection
from media_manager.movies.models import Movie,MovieFile
from media_manager.config import MediaManagerConfig

log=logging.getLogger(__name__)
router=APIRouter(dependencies=[Depends(current_active_user)])
_refresh_lock=threading.Lock()
_progress={'running':False,'updated':0,'error':None}


def tmdb_get(path,key,language='en'):
    if not key:raise ValueError('A TMDB API key is required for direct collection refresh. Configure it in administrator settings or the Docker environment.')
    try:
        response=requests.get('https://api.themoviedb.org/3/'+path,params={'api_key':key,'language':language},timeout=(5,25))
        if response.status_code!=200:raise ValueError(f'TMDB returned HTTP {response.status_code}. Check the API key and retry.')
        return response.json()
    except requests.RequestException:
        # Request exception URLs can contain the API key. Never propagate or log them.
        raise ValueError('TMDB could not be reached. Retry later.') from None
    except (TypeError,requests.exceptions.JSONDecodeError):
        raise ValueError('TMDB returned an invalid response.') from None


def normalized_tmdb(data):
    return dict(id=int(data['id']),name=data['name'],overview=data.get('overview') or '',poster_url='https://image.tmdb.org/t/p/w500'+data['poster_path'] if data.get('poster_path') else None,parts=[dict(tmdb_id=int(p['id']),imdb_id=None,name=p.get('title') or p.get('original_title') or str(p['id']),year=int(p['release_date'][:4]) if p.get('release_date') else None,release_date=p.get('release_date'),poster_url='https://image.tmdb.org/t/p/w500'+p['poster_path'] if p.get('poster_path') else None) for p in data.get('parts',[])],source='tmdb')


def normalized_radarr(data):
    def poster(item):return next((i.get('remoteUrl') or i.get('url') for i in item.get('images',[]) if i.get('coverType')=='poster'),None)
    return dict(id=int(data['tmdbId']),name=data['title'],overview=data.get('overview') or '',poster_url=poster(data),parts=[dict(tmdb_id=int(p['tmdbId']),imdb_id=p.get('imdbId'),name=p['title'],year=p.get('year') or None,release_date=p.get('releaseDate'),status=p.get('status'),poster_url=poster(p)) for p in data.get('movies',[]) if p.get('tmdbId')],source='radarr')


def save_collection(db,data):
    row=db.get(MovieCollection,data['id'])
    if row is None:row=MovieCollection(**data,updated_at=datetime.now(timezone.utc));db.add(row)
    else:
        for k,v in data.items():setattr(row,k,v)
        row.updated_at=datetime.now(timezone.utc)
    db.commit()
    return row


def catalogue(db):
    movies=list(db.scalars(select(Movie)))
    tmdb={m.external_id:m for m in movies if m.metadata_provider=='tmdb'}
    imdb={m.imdb_id:m for m in movies if m.imdb_id}
    # The catalogue tracks original paths. Never use Radarr's independent isExisting flag.
    files={}
    for f in db.scalars(select(MovieFile)):
        files.setdefault(f.movie_id,[]).extend(f.source_files or [])
    return tmdb,imdb,files


def collection_details(db,row,index=None):
    tmdb,imdb,files=index or catalogue(db)
    parts=[]
    for part in row.parts:
        movie=tmdb.get(part['tmdb_id']) or imdb.get(part.get('imdb_id'))
        present=bool(movie and any(Path(p).is_file() for p in files.get(movie.id,[])))
        if movie and not present:
            from media_manager.torrent.models import Torrent
            for record in db.scalars(select(MovieFile).where(MovieFile.movie_id==movie.id)):
                if record.source_files is None:
                    torrent=db.get(Torrent,record.torrent_id) if record.torrent_id else None
                    present=present or record.torrent_id is None or bool(torrent and torrent.imported)
        release=part.get('release_date')
        upcoming=bool(release and release[:10]>date.today().isoformat()) or part.get('status')=='announced' or bool(not part.get('year'))
        parts.append(part|{'movie_id':str(movie.id) if movie else None,'available':present,'state':'available' if present else 'upcoming' if upcoming else 'missing'})
    return {'id':row.id,'name':row.name,'overview':row.overview,'poster_url':row.poster_url,'source':row.source,'updated_at':row.updated_at,'parts':parts,'available_count':sum(p['available'] for p in parts),'missing_count':sum(p['state']=='missing' for p in parts)}


@router.get('')
def list_collections(db:DbSessionDependency):
    index=catalogue(db)
    return [collection_details(db,row,index) for row in db.scalars(select(MovieCollection).order_by(MovieCollection.name))]


@router.get('/refresh-status')
def refresh_status():return dict(_progress)


def refresh_job():
    try:
        from media_manager.database import SessionLocal
        with SessionLocal() as db:
            config=MediaManagerConfig();scan=config.misc.library_scan
            if scan.radarr_url and scan.radarr_api_key:
                try:
                    r=requests.get(scan.radarr_url.rstrip('/')+'/api/v3/collection',headers={'X-Api-Key':scan.radarr_api_key},timeout=(5,30))
                    if r.status_code!=200:raise ValueError('Radarr collection metadata could not be loaded.')
                    for item in r.json():
                        if item.get('tmdbId'):save_collection(db,normalized_radarr(item));_progress['updated']+=1
                except requests.RequestException:raise ValueError('Radarr collection metadata could not be reached.') from None
            key=config.metadata.tmdb.api_key
            if key:
                cached=list(db.scalars(select(MovieCollection)))
                ids={c.id for c in cached}
                known={p['tmdb_id'] for c in cached for p in c.parts}
                for movie in db.scalars(select(Movie).where(Movie.metadata_provider=='tmdb')):
                    if movie.external_id in known:continue
                    data=tmdb_get('movie/'+str(movie.external_id),key,config.metadata.tmdb.default_language)
                    collection=data.get('belongs_to_collection')
                    if collection:ids.add(int(collection['id']))
                for collection_id in sorted(ids):
                    save_collection(db,normalized_tmdb(tmdb_get('collection/'+str(collection_id),key,config.metadata.tmdb.default_language)));_progress['updated']+=1
            elif not _progress['updated']:
                raise ValueError('Configure a TMDB API key or an existing Radarr metadata connection to load movie collections.')
    except ValueError as error:_progress['error']=str(error)
    except Exception:
        _progress['error']='Collection refresh failed. Check the metadata connection and retry.'
        log.warning('Collection refresh failed; credentials and remote response details were withheld.')
    finally:_progress['running']=False;_refresh_lock.release()


@router.post('/refresh',dependencies=[Depends(current_superuser)],status_code=202)
def refresh():
    if not _refresh_lock.acquire(blocking=False):raise HTTPException(409,'A collection refresh is already running.')
    _progress.update(running=True,updated=0,error=None)
    threading.Thread(target=refresh_job,daemon=True,name='collection-refresh').start()
    return dict(_progress)


@router.get('/{collection_id}')
def get_collection(collection_id:int,db:DbSessionDependency):
    row=db.get(MovieCollection,collection_id)
    if row is None:raise HTTPException(404,'Collection not found. Refresh collection metadata first.')
    return collection_details(db,row)
