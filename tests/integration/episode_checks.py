"""Real PostgreSQL/filesystem checks with a fake transport; never downloads real media."""
import importlib,re,tempfile,uuid
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from media_manager.config import MediaManagerConfig
from media_manager.database import init_engine
from media_manager.tv.models import Show,Episode,EpisodeDownload,Season as SeasonModel
from media_manager.tv.repository import TvRepository
from media_manager.tv.service import TvService
from media_manager.tv.monitor import run_show
from media_manager.torrent.repository import TorrentRepository
from media_manager.torrent.service import TorrentService
from media_manager.torrent.schemas import Torrent,TorrentStatus,Quality
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.indexer.config import ReleasePolicyConfig
import media_manager.release_policy as policy_module

engine=init_engine(MediaManagerConfig().database)
now=datetime.now(ZoneInfo('Europe/Berlin'));today=now.date()
series_id=uuid.UUID(SHOW_ID)
with Session(engine) as db:
 row=db.get(Show,series_id);row.continuous_download=True;row.monitor_from=today;row.monitor_checked_at=now
 season=db.scalars(select(SeasonModel).where(SeasonModel.show_id==series_id)).one()
 episodes={e.number:e for e in season.episodes}
 episodes[1].air_date=today-timedelta(days=7);episodes[2].air_date=today
 third=Episode(id=uuid.uuid4(),season_id=season.id,number=3,external_id=9910003,title='Future weekly episode',air_date=today+timedelta(days=7));db.add(third);db.commit()
 sid=season.id;eid=episodes[2].id;first_id=episodes[1].id;third_id=third.id

existing_fixture=MediaManagerConfig().misc.tv_directory/'Own catalogue show'/'Own.S01E02.mkv'
assert existing_fixture.exists();existing_fixture.unlink()
original_config=policy_module.MediaManagerConfig
policy_module.MediaManagerConfig=lambda:SimpleNamespace(indexers=SimpleNamespace(release_policy=ReleasePolicyConfig(enabled=True)))
calls=[]
class Transport:
 fail=False
 def download(self,result):
  calls.append(result.title)
  if self.fail:raise TimeoutError('own simulated ambiguous submission')
  return Torrent(title=result.title,status=TorrentStatus.downloading,quality=result.quality,hash='own-'+str(uuid.uuid4()),imported=False,usenet=result.usenet)
transport=Transport()
class Indexer:
 upgrade=False
 english_only=True
 def search_season(self,query=None,show=None,season_number=None):
  return [r for n in [1,2,3,4] for r in self.search(f'Own.S01E{n:02d}',True)]
 def search(self,query,is_tv):
  ep=int(re.search(r'E(\d+)',query)[1])
  titles=[f'Own.S01E{ep:02d}.English.2160p.WEB',f'Own.S01E{ep:02d}.German.2160p.REMUX']
  if not self.english_only:titles.append(f'Own.S01E{ep:02d}.German.720p.WEB')
  if self.upgrade:titles.append(f'Own.S01E{ep:02d}.German.1080p.WEB')
  return [IndexerQueryResult(title=t,download_url='http://localhost/own.nzb',seeders=0,flags=[],size=1,usenet=True,age=1,indexer='Own fake transport') for t in titles]
indexer=Indexer()
def service(db):return TvService(TvRepository(db),TorrentService(TorrentRepository(db),transport),indexer,Mock())
guard=engine.connect();guard.execute(text('SELECT pg_advisory_lock(194731,501)'))
try:
 with Session(engine) as db:
  svc=service(db);run_show(svc,svc.get_show_by_id(series_id))
  assert calls==['Own.S01E02.English.2160p.WEB'],calls
  job=db.get(EpisodeDownload,eid);assert job.status=='submitted';torrent_id=job.torrent_id
 # A new process/session must retain the claim and avoid submitting the same episode again.
 with Session(engine) as db:
  svc=service(db);run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==1
  source=Path(tempfile.mkdtemp())/'Own.S01E02.mkv';source.write_bytes(b'own synthetic media')
  module=importlib.import_module('media_manager.tv.service');original_files=module.get_files_for_import
  module.get_files_for_import=lambda **kwargs:([source],[],[source])
  try:svc.import_torrent_files(svc.torrent_service.torrent_repository.get_torrent_by_id(torrent_id),svc.get_show_by_id(series_id))
  finally:module.get_files_for_import=original_files
  assert db.get(EpisodeDownload,eid).status=='imported'
  assert svc.torrent_service.torrent_repository.get_torrent_by_id(torrent_id).imported
  assert not svc.is_season_downloaded(sid) # EP3 is still in the future.
  # Same release must not be reacquired; a better German resolution can be upgraded later.
  db.get(EpisodeDownload,eid).checked_at=now-timedelta(hours=7);db.commit()
  run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==1
  indexer.english_only=False;db.get(EpisodeDownload,eid).checked_at=now-timedelta(hours=7);db.commit()
  run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==2 and calls[-1]=='Own.S01E02.German.720p.WEB' # German outranks the already imported English 2160p.
  current_torrent=db.get(EpisodeDownload,eid).torrent_id
  module.get_files_for_import=lambda **kwargs:([source],[],[source])
  try:svc.import_torrent_files(svc.torrent_service.torrent_repository.get_torrent_by_id(current_torrent),svc.get_show_by_id(series_id))
  finally:module.get_files_for_import=original_files
  indexer.upgrade=True;db.get(EpisodeDownload,eid).checked_at=now-timedelta(hours=7);db.commit()
  run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==3 and calls[-1]=='Own.S01E02.German.1080p.WEB'
  # Simulate the next weekly release within the same existing season.
  db.get(Episode,third_id).air_date=today;db.commit()
  run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==4 and 'S01E03' in calls[-1]
  fourth=Episode(id=uuid.uuid4(),season_id=sid,number=4,external_id=9910004,title='Uncertain test',air_date=today);db.add(fourth);db.commit();db.expire_all()
  transport.fail=True;run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==5
  assert db.get(EpisodeDownload,fourth.id).status=='uncertain'
  run_show(svc,svc.get_show_by_id(series_id));assert len(calls)==5
  assert db.get(EpisodeDownload,first_id) is None # no unsolicited old-episode backfill
 print('episode-monitor: weekly continuation, priority, import, upgrade, durable claim, uncertain submission, no backfill passed')
finally:
 policy_module.MediaManagerConfig=original_config
 guard.execute(text('SELECT pg_advisory_unlock(194731,501)'));guard.close()
