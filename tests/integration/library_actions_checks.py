"""Synthetic real-PostgreSQL checks; never contact actual download managers."""
from uuid import uuid4
from datetime import date,timedelta,datetime,timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from fastapi import HTTPException,BackgroundTasks
from media_manager.database import init_engine
from media_manager.config import MediaManagerConfig
from media_manager.tv.models import Show,Season,Episode,SeasonFile
from media_manager.tv.repository import TvRepository
from media_manager.tv.service import TvService
from media_manager.library_models import ShowExternalId,EpisodeRequest,MovieCollection
from media_manager.show_identity import resolve,register,merge_empty_duplicate
from media_manager.library_availability import public_show
from media_manager.movie_collections import normalized_tmdb,save_collection,collection_details
from media_manager.movies.models import Movie,MovieFile
from media_manager.auth.db import User
from media_manager.auth.request_policy import usage_count
from media_manager.episode_requests import request_episode,EpisodeRequestCreate,delete_request,approve,Approval
from media_manager.torrent.schemas import Quality
from pathlib import Path
engine=init_engine(MediaManagerConfig().database)
with Session(engine) as db:
 assert db.scalar(text('select version_num from alembic_version'))=='c7d543ae845e'
 keep=Show(id=uuid4(),name='Identity fixture',external_id=111112,metadata_provider='tvdb',imdb_id='tt99901112',overview='',year=2025)
 duplicate=Show(id=uuid4(),name='Same fixture',external_id=222223,metadata_provider='tmdb',imdb_id=keep.imdb_id,overview='',year=2025)
 db.add_all([keep,duplicate]);db.commit()
 season=Season(id=uuid4(),show_id=keep.id,number=1,external_id=111,name='Season one',overview='')
 special=Season(id=uuid4(),show_id=keep.id,number=0,external_id=112,name='Specials',overview='')
 db.add_all([season,special]);db.flush()
 episodes=[Episode(id=uuid4(),season_id=season.id,number=n,external_id=100+n,title='Fixture '+str(n),air_date=date.today()+timedelta(days=7) if n==3 else date.today()-timedelta(days=7)) for n in [1,2,3]]
 db.add_all(episodes);db.commit()
 root=MediaManagerConfig().misc.tv_directory/'Identity fixture';root.mkdir(exist_ok=True)
 video=root/'Fixture.S01E01.mkv';video.write_bytes(b'synthetic fixture')
 file=SeasonFile(season_id=season.id,file_path_suffix='',quality=Quality.fullhd,source_files=[str(video)],episode_numbers=[1]);db.add(file);db.commit()
 original_ids=(keep.id,season.id,episodes[0].id)
 result=merge_empty_duplicate(db,keep,duplicate);db.commit()
 assert not result['files_changed'] and db.get(Show,duplicate.id) is None
 assert resolve(db,{'tmdb':'222223'}).id==keep.id
 assert resolve(db,{'tvdb':'111112'}).id==keep.id
 assert video.read_bytes()==b'synthetic fixture'
 service=TvService.__new__(TvService);service.tv_repository=TvRepository(db)
 dto=public_show(service,service.tv_repository.get_show_by_id(keep.id))
 assert len(dto.seasons)==1 and dto.seasons[0].number==1
 assert [e.state for e in dto.seasons[0].episodes]==['available','missing','upcoming']
 assert dto.external_ids['tmdb']=='222223' and dto.id==original_ids[0]
 # Provider search and add both return canonical series IDs.
 provider=Mock();provider.name='tmdb'
 provider.search_show.return_value=[]
 provider.get_show_metadata.return_value=service.tv_repository.get_show_by_id(keep.id).model_copy(update={'external_id':222223,'metadata_provider':'tmdb'})
 assert service.add_show(222223,provider).id==keep.id
 # Individual episode requests share the existing monthly ledger and survive cancellation.
 user=User(id=uuid4(),email='episode-fixture@example.com',hashed_password='unused',is_active=True,is_superuser=False,is_verified=True,monthly_request_limit=1,auto_approve_requests=False)
 db.add(user);db.commit()
 body=EpisodeRequestCreate(episode_id=episodes[1].id,min_quality=Quality.hd,wanted_quality=Quality.fullhd)
 r=request_episode(body,service,user,BackgroundTasks());assert not r['authorized'] and usage_count(db,user.id)==1
 assert db.get(EpisodeRequest,__import__('uuid').UUID(r['id'])).episode_id==episodes[1].id
 # More episodes of this season are free, even when the monthly limit is reached.
 additional=request_episode(EpisodeRequestCreate(episode_id=episodes[2].id,min_quality=Quality.hd,wanted_quality=Quality.fullhd),service,user,BackgroundTasks())
 assert additional['id'] and usage_count(db,user.id)==1
 other_season=Season(id=uuid4(),show_id=keep.id,number=2,external_id=500,name='Next season',overview='');db.add(other_season);db.flush()
 other_episode=Episode(id=uuid4(),season_id=other_season.id,number=1,external_id=501,title='Next season episode');db.add(other_episode);db.commit()
 try:request_episode(EpisodeRequestCreate(episode_id=other_episode.id,min_quality=Quality.hd,wanted_quality=Quality.fullhd),service,user,BackgroundTasks())
 except HTTPException as error:assert error.status_code==429;db.rollback()
 else:raise AssertionError('Different season quota bypass')
 delete_request(__import__('uuid').UUID(r['id']),db,user)
 assert usage_count(db,user.id)==1
 # Exact-ID collection matching, physical-file presence and future members.
 movie=Movie(id=uuid4(),name='Collection fixture',external_id=111113,metadata_provider='tmdb',imdb_id='tt99901113',overview='',year=2020)
 db.add(movie);db.commit()
 moviepath=MediaManagerConfig().misc.movie_directory/'Collection-fixture.mkv';moviepath.write_bytes(b'synthetic')
 db.add(MovieFile(movie_id=movie.id,file_path_suffix='',quality=Quality.fullhd,source_files=[str(moviepath)]));db.commit()
 row=save_collection(db,normalized_tmdb({'id':99901113,'name':'Fixture collection','parts':[{'id':111113,'title':'Present','release_date':'2020-01-01'},{'id':111114,'title':'Missing','release_date':'2021-01-01'},{'id':111115,'title':'Future','release_date':'2099-01-01'}]}))
 details=collection_details(db,row);assert [p['state'] for p in details['parts']]==['available','missing','upcoming']
 assert details['parts'][0]['movie_id']==str(movie.id)
 moviepath.unlink();assert collection_details(db,row)['parts'][0]['state']=='missing'
 # Refuse destructive automatic merging of a duplicate with any recorded files.
 other=Show(id=uuid4(),name='Referenced duplicate',external_id=222224,metadata_provider='tmdb',imdb_id=keep.imdb_id,overview='',year=2025)
 db.add(other);db.flush();s=Season(id=uuid4(),show_id=other.id,number=1,external_id=113,name='',overview='');db.add(s);db.flush();db.add(SeasonFile(season_id=s.id,file_path_suffix='',quality=Quality.fullhd,source_files=[str(video)]));db.commit()
 try:merge_empty_duplicate(db,keep,other)
 except HTTPException as error:assert error.status_code==409
 else:raise AssertionError('Referenced duplicate was deleted')
 assert db.get(Show,other.id) and video.exists()
print('library identity, episode availability, quota and collection checks passed')
