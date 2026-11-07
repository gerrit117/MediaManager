"""Authenticated discovery using documented TMDB lists and country-specific watch providers."""
from copy import deepcopy
from datetime import datetime,timedelta
import hashlib,json,threading,time
from typing import Literal
from zoneinfo import ZoneInfo
import requests
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from media_manager.auth.users import current_active_user
from media_manager.config import MediaManagerConfig
from media_manager.database import DbSessionDependency
from media_manager.movies.models import Movie
from media_manager.tv.models import Show
from media_manager.library_models import ShowExternalId

router=APIRouter(dependencies=[Depends(current_active_user)])
_cache={}
_cache_lock=threading.Lock()
Kind=Literal['movie','tv']
Mode=Literal['trending','popular','top_rated','recent']
Language=Literal['de','en']


def tmdb(path,params=None,ttl=600):
    key=MediaManagerConfig().metadata.tmdb.api_key
    if not key:raise HTTPException(503,'A TMDB API key is required for discovery. An administrator can configure it in Settings or the Docker environment.')
    params=dict(params or {})
    cache_key=(hashlib.sha256(key.encode()).hexdigest(),path,json.dumps(params,sort_keys=True))
    now=time.monotonic()
    with _cache_lock:
        item=_cache.get(cache_key)
        if item and now-item[0]<ttl:return deepcopy(item[1])
    try:
        response=requests.get('https://api.themoviedb.org/3/'+path,params=params|{'api_key':key},timeout=(5,20))
        if response.status_code==429:raise HTTPException(503,'TMDB request limit reached. Please try again later.')
        if response.status_code in [401,403]:raise HTTPException(502,'TMDB rejected the API key. An administrator should check the configured key.')
        if response.status_code!=200:raise HTTPException(502,'TMDB could not load this selection. Please try again later.')
        data=response.json()
        if not isinstance(data,dict):raise HTTPException(502,'TMDB returned an invalid response.')
    except (requests.RequestException,ValueError):
        # Request URLs can contain the API key. Never log/return exception or response bodies.
        raise HTTPException(502,'TMDB could not be reached. Please try again later.') from None
    with _cache_lock:
        if len(_cache)>=128:_cache.pop(next(iter(_cache)))
        _cache[cache_key]=(now,deepcopy(data))
    return data


def list_query(kind,mode,window,page,region,provider_id,company_id,genre_id,min_votes):
    language_key='first_air_date' if kind=='tv' else 'primary_release_date'
    filters=any([provider_id,company_id,genre_id])
    if mode=='trending':
        if filters:raise HTTPException(422,'Choose Popular, Top rated or Recently released to use catalogue filters.')
        if page!=1:raise HTTPException(422,'Trending shows one current list. Choose a catalogue list to browse more pages.')
        return f'trending/{kind}/{window}',{}
    params={'page':page,'include_adult':'false','sort_by':'popularity.desc','vote_count.gte':min_votes}
    if mode=='top_rated':params['sort_by']='vote_average.desc'
    if mode=='recent':
        today=datetime.now(ZoneInfo('Europe/Berlin')).date()
        params.update({'sort_by':language_key+'.desc',language_key+'.gte':(today-timedelta(days=365)).isoformat(),language_key+'.lte':today.isoformat()})
    if provider_id:params.update({'with_watch_providers':str(provider_id),'watch_region':region,'with_watch_monetization_types':'flatrate'})
    if company_id:params['with_companies']=str(company_id)
    if genre_id:params['with_genres']=str(genre_id)
    return 'discover/'+kind,params


def library_ids(db,kind):
    model=Show if kind=='tv' else Movie
    owned={int(external):str(internal) for internal,external in db.execute(select(model.id,model.external_id).where(model.metadata_provider=='tmdb'))}
    if kind=='tv':owned.update({int(external):str(internal) for external,internal in db.execute(select(ShowExternalId.external_id,ShowExternalId.show_id).where(ShowExternalId.provider=='tmdb')) if str(external).isdigit()})
    return owned


def format_results(data,kind,owned):
    results=[]
    for entry in data.get('results',[]):
        if not isinstance(entry,dict) or entry.get('adult') or not isinstance(entry.get('id'),int):continue
        name=entry.get('name') if kind=='tv' else entry.get('title')
        if not name:continue
        external=entry['id'];date=entry.get('first_air_date') if kind=='tv' else entry.get('release_date');poster=entry.get('poster_path')
        results.append({'name':name,'overview':entry.get('overview') or '', 'external_id':external,'metadata_provider':'tmdb','id':owned.get(external),'added':external in owned,'poster_path':'https://image.tmdb.org/t/p/w500'+poster if poster else None,'year':int(date[:4]) if date and date[:4].isdigit() else None,'vote_average':entry.get('vote_average'),'original_language':entry.get('original_language')})
    return results


@router.get('/companies')
def companies(query:str=Query(min_length=2,max_length=100)):
    data=tmdb('search/company',{'query':query,'page':1},ttl=3600)
    return [{'id':c['id'],'name':c['name'],'country':c.get('origin_country') or ''} for c in data.get('results',[]) if isinstance(c.get('id'),int) and c.get('name')][:20]


@router.get('/{kind}/options')
def options(kind:Kind,region:str=Query('DE',pattern='^[A-Z]{2}$'),language:Language='de'):
    providers=tmdb('watch/providers/'+kind,{'watch_region':region,'language':'de-DE' if language=='de' else 'en-US'},ttl=86400)
    genres=tmdb('genre/'+kind+'/list',{'language':'de-DE' if language=='de' else 'en-US'},ttl=86400)
    regions=tmdb('watch/providers/regions',ttl=86400)
    items=sorted(providers.get('results',[]),key=lambda p:(p.get('display_priorities',{}).get(region,p.get('display_priority',999)),p.get('provider_name','')))
    return {'providers':[{'id':p['provider_id'],'name':p['provider_name'],'logo':'https://image.tmdb.org/t/p/w92'+p['logo_path'] if p.get('logo_path') else None} for p in items], 'genres':[{'id':g['id'],'name':g['name']} for g in genres.get('genres',[])],'regions':[{'id':r['iso_3166_1'],'name':r.get('native_name') or r.get('english_name') or r['iso_3166_1']} for r in regions.get('results',[])],'region':region}


@router.get('/{kind}')
def discover(kind:Kind,db:DbSessionDependency,mode:Mode='trending',window:Literal['day','week']='week',page:int=Query(1,ge=1,le=500),region:str=Query('DE',pattern='^[A-Z]{2}$'),language:Language='de',provider_id:int|None=Query(None,ge=1),company_id:int|None=Query(None,ge=1),genre_id:int|None=Query(None,ge=1),min_votes:int=Query(100,ge=0,le=10000)):
    path,params=list_query(kind,mode,window,page,region,provider_id,company_id,genre_id,min_votes)
    data=tmdb(path,params|{'language':'de-DE' if language=='de' else 'en-US'})
    return {'results':format_results(data,kind,library_ids(db,kind)),'page':1 if mode=='trending' else data.get('page',page),'total_pages':1 if mode=='trending' else min(int(data.get('total_pages') or 0),500),'total_results':data.get('total_results',0),'mode':mode,'window':window if mode=='trending' else None,'source':'TMDB','region':region,'availability_source':'JustWatch' if provider_id else None}
