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
 print('bulk-library: async import, NFO/HTTP identities, secrets, no file changes, idempotence, persistent mappings and manual review passed')
finally:server.shutdown();server.server_close()
