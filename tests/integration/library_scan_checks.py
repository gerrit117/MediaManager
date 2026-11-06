"""Asynchronous, persistent library import using real PostgreSQL and a read-only HTTP metadata fixture."""
import json,threading,time,uuid,urllib.parse
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import requests
from sqlalchemy.orm import Session
from sqlalchemy import select,func
from media_manager.database import init_engine
from media_manager.config import MediaManagerConfig
from media_manager.movies.models import Movie,MovieFile
from media_manager.tv.models import Show,Season,Episode,SeasonFile
from media_manager.library_scan import known_directories
cfg=MediaManagerConfig();dbengine=init_engine(cfg.database)
film=cfg.misc.movie_directory/'Own bulk film';film.mkdir(exist_ok=True);(film/'Own bulk film.mkv').write_bytes(b'own catalogue fixture');(film/'movie.nfo').write_text('<movie><title>Own bulk film</title><year>2026</year><tmdbid>9876543</tmdbid></movie>')
series=cfg.misc.tv_directory/'Own bulk show';series.mkdir(exist_ok=True);(series/'Own.S01E01.mkv').write_bytes(b'own weekly fixture')
ambiguous=cfg.misc.movie_directory/'Own ambiguous folder';ambiguous.mkdir(exist_ok=True);(ambiguous/'Unknown.mkv').write_bytes(b'own unidentifiable fixture')
from PIL import Image
Image.new('RGB',(48,72),'#26666a').save(series/'poster.jpg')
before={str(p):(p.stat().st_ino,p.read_bytes()) for root in [film,series,ambiguous] for p in root.iterdir() if p.is_file()}
requests_seen=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  requests_seen.append(self.path)
  assert self.headers.get('X-Api-Key')=='own-test-source-key'
  if self.path=='/api/v3/series':data=[{'id':1,'tvdbId':987654,'title':'Own bulk show','year':2026,'path':'/media/Own bulk show','overview':'Own trusted metadata','ended':False}]
  elif self.path=='/api/v3/episode?seriesId=1':data=[{'tvdbId':999777,'seasonNumber':1,'episodeNumber':1,'title':'Own pilot','airDate':'2026-11-06'},{'tvdbId':999778,'seasonNumber':1,'episodeNumber':2,'title':'Future episode','airDate':'2099-01-01'}]
  else:self.send_response(404);self.end_headers();return
  raw=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
session=requests.Session();base='http://127.0.0.1:8000';assert session.post(base+'/api/v1/auth/cookie/login',data={'username':'admin@example.com','password':ADMIN_PASSWORD}).status_code==204
try:
 values={'misc.library_scan.sonarr_url':'http://127.0.0.1:'+str(server.server_port),'misc.library_scan.sonarr_api_key':'own-test-source-key','misc.library_scan.automatic':False}
 result=session.put(base+'/api/v1/settings',json={'values':values});assert result.status_code==200 and not result.json()['restart_required']
 fields=session.get(base+'/api/v1/settings').json()['fields'];key=next(f for f in fields if f['key']=='misc.library_scan.sonarr_api_key');assert key['value'] is None and key['configured']
 member=requests.Session();assert member.post(base+'/api/v1/auth/cookie/login',data={'username':'user@example.com','password':ADMIN_PASSWORD}).status_code==204
 assert member.post(base+'/api/v1/library/scan').status_code==403
 assert member.get(base+'/api/v1/library/scan').status_code==403
 assert member.get(base+'/api/v1/library/summary').status_code==200
 assert session.post(base+'/api/v1/library/scan?mode=reorganize').status_code==400
 assert session.post(base+'/api/v1/library/scan',headers={'Origin':'http://foreign.invalid'}).status_code==403
 def run():
  assert session.post(base+'/api/v1/library/scan?mode=catalogue').status_code==202
  for _ in range(300):
   status=session.get(base+'/api/v1/library/scan').json()
   if status['status']!='running':break
   time.sleep(.1)
  assert status['status']=='completed',status
  return status
 first=run();assert first['imported']>=2,first
 assert any(row['directory']==str(ambiguous) for row in first['review'])
 assert before=={str(p):(p.stat().st_ino,p.read_bytes()) for root in [film,series,ambiguous] for p in root.iterdir() if p.is_file()}
 with Session(dbengine) as db:
  movie=db.scalars(select(Movie).where(Movie.external_id==9876543)).one();show=db.scalars(select(Show).where(Show.external_id==987654)).one();mid=movie.id;sid=show.id
  assert not show.continuous_download
  assert len(show.seasons)==1 and len(show.seasons[0].episodes)==2
  assert len(db.scalars(select(SeasonFile).join(Season).where(Season.show_id==sid)).all())==1
  assert known_directories(db,cfg.misc.tv_directory,'tv')['Own bulk show']==sid
 second=run()
 with Session(dbengine) as db:
  assert db.scalar(select(func.count(Movie.id)).where(Movie.external_id==9876543))==1
  assert db.scalar(select(func.count(Show.id)).where(Show.external_id==987654))==1
  assert db.get(Show,sid).seasons[0].episodes[0].id
 # Source services can be removed after migration: stored file mappings still resolve existing series.
 assert session.put(base+'/api/v1/settings',json={'values':{'misc.library_scan.sonarr_url':''}}).status_code==200
 third=run();assert not any(r['directory']==str(series) for r in third['review'])
 assert before=={str(p):(p.stat().st_ino,p.read_bytes()) for root in [film,series,ambiguous] for p in root.iterdir() if p.is_file()}
 # Partial seasons already catalogued must not reappear as import suggestions.
 suggestions=session.get(base+'/api/v1/tv/importable?discover_only=true').json()
 assert not any(row['directory']==str(series) for row in suggestions)
 endpoint=base+'/api/v1/library/metadata/tv/'+str(sid)
 body={'provider':'tvdb','external_id':987654,'previous_provider':'tvdb','previous_external_id':987654,'name':'Own edited title','year':2025,'overview':'Own edited overview'}
 assert member.put(endpoint,json=body).status_code==403
 assert member.get(endpoint+'/preview?provider=tvdb&external_id=987654').status_code==403
 assert session.put(endpoint,json=body).status_code==200
 with Session(dbengine) as db:
  assert db.get(Show,sid).name=='Own edited title' and db.get(Show,sid).year==2025
 edited=run();assert not edited['errors']
 with Session(dbengine) as db:
  assert db.get(Show,sid).name=='Own edited title' and db.get(Show,sid).year==2025
 # Exercise provider reassignment with real PostgreSQL but deterministic local metadata.
 import media_manager.library_metadata as metadata
 from media_manager.library_metadata import MetadataEdit,edit_metadata
 from media_manager.library_scan import build_show
 from types import SimpleNamespace
 from fastapi import HTTPException
 real_load,real_provider=metadata.load_metadata,metadata.get_metadata_provider
 try:
  fresh=build_show({'tmdbId':888777,'title':'Own corrected show','year':2026},[{'seasonNumber':1,'episodeNumber':1,'title':'Own corrected pilot','airDate':'2026-11-06'},{'seasonNumber':1,'episodeNumber':2,'title':'Future corrected','airDate':'2099-01-01'}])
  fresh.seasons[0].external_id=888001;fresh.seasons[0].episodes[0].external_id=888002
  metadata.load_metadata=lambda *a,**k:fresh
  metadata.get_metadata_provider=lambda *a:SimpleNamespace(download_show_poster_image=lambda **kw:False)
  with Session(dbengine) as db:
   old=db.get(Show,sid);season_id=old.seasons[0].id;episode_ids=[e.id for e in old.seasons[0].episodes]
   params=body|{'provider':'tmdb','external_id':888777,'name':'Own corrected show','year':2026,'refresh_metadata':True,'confirm_identity_change':True}
   assert edit_metadata('tv',sid,MetadataEdit(**params),db)['saved']
   db.expire_all();corrected=db.get(Show,sid)
   assert corrected.metadata_provider=='tmdb' and corrected.external_id==888777
   assert corrected.seasons[0].id==season_id and [e.id for e in corrected.seasons[0].episodes]==episode_ids
   assert not corrected.continuous_download and corrected.library=='Default'
   assert db.scalars(select(SeasonFile).where(SeasonFile.season_id==season_id)).one().source_files==[str(series/'Own.S01E01.mkv')]
   try:edit_metadata('tv',sid,MetadataEdit(**params),db)
   except HTTPException as error:assert error.status_code==409;db.rollback()
   else:raise AssertionError('Concurrent stale edit accepted')
   existing_movie=db.get(Movie,mid)
   duplicate=body|{'provider':existing_movie.metadata_provider,'external_id':existing_movie.external_id,'previous_provider':'tmdb','previous_external_id':888777}
   # Duplicate identity rejection is checked using a second TV record.
   other=Show(id=uuid.uuid4(),external_id=222111,metadata_provider='tmdb',name='Own existing identity',overview='',year=2026,library='Default');db.add(other);db.commit()
   duplicate=body|{'provider':'tmdb','external_id':222111,'previous_provider':'tmdb','previous_external_id':888777,'confirm_identity_change':True}
   try:edit_metadata('tv',sid,MetadataEdit(**duplicate),db)
   except HTTPException as error:assert error.status_code==409;db.rollback()
   else:raise AssertionError('Duplicate identity accepted')
   db.delete(db.get(Show,other.id));db.commit()
 finally:metadata.load_metadata,metadata.get_metadata_provider=real_load,real_provider
 # Re-enable the source. Its old ID must not undo a saved correction or create a duplicate show.
 assert session.put(base+'/api/v1/settings',json={'values':{'misc.library_scan.sonarr_url':'http://127.0.0.1:'+str(server.server_port)}}).status_code==200
 fourth=run();assert not fourth['errors']
 with Session(dbengine) as db:
  assert db.get(Show,sid).external_id==888777
  assert db.scalar(select(func.count(Show.id)).where(Show.external_id==987654))==0
 assert before=={str(p):(p.stat().st_ino,p.read_bytes()) for root in [film,series,ambiguous] for p in root.iterdir() if p.is_file()}
 print('metadata-details: admin editing, reassignment, stable keys/files, stale edit and duplicate rejection, correction survives scan passed')
 print('bulk-library: async import, NFO/HTTP identities, secrets, no file changes, idempotence, persistent mappings and manual review passed')
finally:server.shutdown();server.server_close()
