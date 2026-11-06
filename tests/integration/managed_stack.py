"""Isolated end-to-end stack + quota test. Uses only synthetic users/media."""
import concurrent.futures,http.cookiejar,json,os,secrets,shutil,socket,subprocess,sys,tempfile,time,urllib.error,urllib.parse,urllib.request,uuid
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
root=Path(tempfile.mkdtemp(prefix='mm-managed-test-',dir=os.getenv('MM_TEST_ROOT')))
project='mmtest-'+uuid.uuid4().hex[:10]
compose=[os.environ['MM_TEST_COMPOSE_BINARY']] if os.getenv('MM_TEST_COMPOSE_BINARY') else ['docker','compose']
with socket.socket() as sock:sock.bind(('',0));port=sock.getsockname()[1]
host=os.getenv('MM_TEST_HOST','127.0.0.1');base=f'http://{host}:{port}'
password=secrets.token_hex(16)
def request(client,path,body=None,method='GET'):
 data=json.dumps(body).encode() if body is not None else None
 try:
  r=client.open(urllib.request.Request(base+path,data,headers={'Content-Type':'application/json'} if body is not None else {},method=method),timeout=10)
  raw=r.read();return r.status,json.loads(raw) if raw else None
 except urllib.error.HTTPError as e:
  raw=e.read();return e.code,json.loads(raw) if raw else None

def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def login(email):
 c=client();r=c.open(base+'/api/v1/auth/cookie/login',urllib.parse.urlencode({'username':email,'password':password}).encode());assert r.status==204;return c

def run(*args,**kw):return subprocess.check_output(args,stderr=subprocess.STDOUT,**kw).decode()
def stack(*args):return run(*compose,'--env-file',str(root/'state/stack.env'),'-f',str(repo/'compose.managed.yaml'),*args)
def exec_python(code):
 code='import media_manager.auth.request_policy;import media_manager.movies.models;import media_manager.tv.models;import media_manager.torrent.models;\n'+code
 service=stack('ps','-q','mediamanager').strip()
 return run('docker','exec','-i',service,'/app/.venv/bin/python','-c',code)
try:
 for name in ['movies','tv','downloads']:
  p=root/name;p.mkdir();os.chown(p,99,100)
 command=[sys.executable,str(repo/'ops/setup-stack.py'),'--directory',str(root/'state'),'--movies',str(root/'movies'),'--tv',str(root/'tv'),'--downloads',str(root/'downloads'),'--project-name',project,'--port',str(port)]
 if os.getenv('MM_TEST_COMPOSE_BINARY'):command+=['--compose-binary',os.environ['MM_TEST_COMPOSE_BINARY']]
 env=dict(os.environ,MM_IMAGE=os.getenv('MM_TEST_IMAGE','mediamanager:1.12.3-fork.3'))
 subprocess.run(command,env=env,stdout=subprocess.DEVNULL,check=True)
 c=client()
 for _ in range(80):
  try:
   if 'Willkommen' in c.open(base).read().decode():break
  except Exception:pass
  time.sleep(1)
 else:raise AssertionError('Setup server unavailable')
 setup=dict(code=(root/'state/config/setup-code').read_text(),admin_email='admin@example.com',admin_password=password)
 status,data=request(c,'/setup/complete',setup,'POST');assert status==200,(status,data)
 for _ in range(90):
  try:
   r=c.open(base+'/api/v1/health',timeout=2)
   if r.headers.get('content-type','').startswith('application/json'):break
  except Exception:pass
  time.sleep(1)
 else:raise AssertionError('Application startup failed')
 admin=login('admin@example.com')
 apppass=(root/'state/secrets/app_db_password').read_text()
 # The application role must not be superuser or be able to create other roles/databases.
 assert exec_python("from media_manager.config import MediaManagerConfig;import psycopg;c=MediaManagerConfig().database;conn=psycopg.connect(host=c.host,port=c.port,dbname=c.dbname,user=c.user,password=c.password);assert conn.execute('select rolsuper,rolcreatedb,rolcreaterole from pg_roles where rolname=current_user').fetchone()==(False,False,False);print('least privilege verified')").strip()=='least privilege verified'
 movies=[str(uuid.uuid4()) for _ in range(12)];show=str(uuid.uuid4());season=str(uuid.uuid4())
 code="""import json,uuid
from sqlalchemy.orm import Session
from media_manager.config import MediaManagerConfig
from media_manager.database import init_engine
import media_manager.auth.request_policy
from media_manager.movies.models import Movie
from media_manager.tv.models import Show,Season
from media_manager.torrent.models import Torrent
engine=init_engine(MediaManagerConfig().database)
with Session(engine) as db:
 for n,i in enumerate(IDS):db.add(Movie(id=uuid.UUID(i),external_id=9000000+n,metadata_provider='tmdb',name='Own synthetic movie '+str(n),overview='Own regression data',year=2026,library='Default'))
 db.add(Show(id=uuid.UUID(SHOW),external_id=9900000,metadata_provider='tmdb',name='Own synthetic show',overview='Own test',year=2026))
 db.flush();db.add(Season(id=uuid.UUID(SEASON),show_id=uuid.UUID(SHOW),number=1,external_id=9900001,name='Own season',overview='Own test'));db.commit()
""".replace('IDS',repr(movies)).replace('SHOW',repr(show)).replace('SEASON',repr(season))
 exec_python(code)
 # Exercise both import modes using disposable files only, never a real media mount.
 def scan_fixture(area, dirname, names):
  folder=root/area/dirname;folder.mkdir();os.chown(folder,99,100)
  for name in names:
   path=folder/name;path.write_bytes(b'own synthetic media fixture');os.chown(path,99,100)
  return folder
 cat=scan_fixture('movies','Own catalogue movie',['original.mkv','archive.rar'])
 reorganize=scan_fixture('movies','Own reorganized movie',['original.mkv'])
 series=scan_fixture('tv','Own catalogue show',['Own.S01E01.mkv'])
 original={p.name:(p.stat().st_ino,p.read_bytes()) for p in cat.iterdir()}
 # Resolve actual container paths from the managed setup config, not host assumptions.
 container_paths=json.loads(exec_python("import json;from media_manager.config import MediaManagerConfig;c=MediaManagerConfig().misc;print(json.dumps([str(c.movie_directory),str(c.tv_directory)]))"))
 status,discovered=request(admin,'/api/v1/movies/importable?discover_only=true');assert status==200 and len(discovered)>=2 and all(not item['candidates'] for item in discovered)
 status,discovered=request(admin,'/api/v1/tv/importable?discover_only=true');assert status==200 and discovered and all(not item['candidates'] for item in discovered)
 catalogue_path=container_paths[0]+'/Own catalogue movie'
 def import_media(area,mid,directory,mode=None):
  query={'directory':directory}
  if mode is not None:query['mode']=mode
  return request(admin,'/api/v1/'+area+'/importable/'+mid+'?'+urllib.parse.urlencode(query),method='POST')
 assert import_media('movies',movies[8],catalogue_path)[0]==204
 assert original=={p.name:(p.stat().st_ino,p.read_bytes()) for p in cat.iterdir()}
 assert import_media('movies',movies[8],catalogue_path,'catalogue')[0]==204 # repeat is idempotent
 assert import_media('movies',movies[8],catalogue_path,'invalid')[0]==422
 assert import_media('movies',movies[8],'/etc','catalogue')[0]==400
 assert import_media('movies',movies[9],container_paths[0]+'/Own reorganized movie','reorganize')[0]==204
 assert not reorganize.exists() and (reorganize.parent/('.'+reorganize.name)).is_dir()
 # A partial season is stored without falsely marking the whole season available.
 exec_python("import uuid;import media_manager.auth.request_policy;from media_manager.torrent.models import Torrent;from sqlalchemy.orm import Session;from media_manager.config import MediaManagerConfig;from media_manager.database import init_engine;from media_manager.tv.models import Episode;e=init_engine(MediaManagerConfig().database);db=Session(e);db.add_all([Episode(id=uuid.uuid4(),season_id=uuid.UUID("+repr(season)+"),number=n,external_id=9910000+n,title='Own episode') for n in [1,2]]);db.commit()")
 series_path=container_paths[1]+'/Own catalogue show'
 assert import_media('tv',show,series_path)[0]==204
 code="from sqlalchemy.orm import Session;from media_manager.config import MediaManagerConfig;from media_manager.database import init_engine;from media_manager.tv.repository import TvRepository;from media_manager.tv.service import TvService;import uuid;e=init_engine(MediaManagerConfig().database);s=TvService.__new__(TvService);s.tv_repository=TvRepository(Session(e));assert s.is_season_downloaded(uuid.UUID("+repr(season)+")) == EXPECTED;print('verified')"
 assert exec_python(code.replace('EXPECTED','False')).strip()=='verified'
 (series/'Own.S01E02.mkv').write_bytes(b'own second fixture');os.chown(series/'Own.S01E02.mkv',99,100)
 assert import_media('tv',show,series_path)[0]==204
 assert exec_python(code.replace('EXPECTED','True')).strip()=='verified'
 (series/'Own.S01E01.mkv').unlink()
 assert exec_python(code.replace('EXPECTED','False')).strip()=='verified'
 def new_user(email):
  status,data=request(client(),'/api/v1/auth/register',{'email':email,'password':password},'POST');assert status==201,(status,data)
  uid=data['id'];assert request(admin,'/api/v1/users/'+uid,{'is_active':True,'is_verified':True},'PATCH')[0]==200
  return uid,login(email)
 created_status,created_data=request(admin,'/api/v1/users/admin-create',{'email':'created@example.com','password':password,'monthly_request_limit':4,'auto_approve_requests':True},'POST')
 assert created_status==201,(created_status,created_data)
 assert 'password' not in created_data and 'hashed_password' not in created_data
 created_client=login('created@example.com');created_quota=request(created_client,'/api/v1/requests/quota')[1]
 assert created_quota['limit']==4 and created_quota['auto_approve']
 assert request(admin,'/api/v1/users/admin-create',{'email':'CREATED@example.com','password':password},'POST')[0]==409
 uid,user=new_user('user@example.com')
 assert request(user,'/api/v1/users/admin-create',{'email':'blocked@example.com','password':password},'POST')[0]==403
 assert request(client(),'/api/v1/users/admin-create',{'email':'blocked@example.com','password':password},'POST')[0]==401
 policy='/api/v1/users/'+uid+'/request-policy'
 assert request(admin,policy,{'monthly_request_limit':2,'auto_approve_requests':True},'PUT')[0]==200
 payload=lambda mid:{'movie_id':mid,'min_quality':3,'wanted_quality':2}
 status,created=request(user,'/api/v1/movies/requests',payload(movies[0]),'POST');assert status==201,(status,created);assert created['authorized'];rid=created['id']
 status,data=request(user,'/api/v1/tv/seasons/requests',{'season_id':season,'min_quality':3,'wanted_quality':2},'POST');assert status==204,(status,data)
 assert request(user,'/api/v1/movies/requests',payload(movies[1]),'POST')[0]==429
 assert request(user,'/api/v1/requests/quota')[1]['used']==2
 assert request(admin,'/api/v1/movies/requests/'+rid,method='DELETE')[0]==204
 assert request(user,'/api/v1/requests/quota')[1]['used']==2
 assert request(user,policy,{'monthly_request_limit':None,'auto_approve_requests':True},'PUT')[0]==403
 # Safe self-update ignores policy/admin fields.
 request(user,'/api/v1/users/me',{'monthly_request_limit':None,'auto_approve_requests':False,'is_superuser':True},'PATCH')
 me=request(user,'/api/v1/users/me')[1];assert not me['is_superuser'];assert me['monthly_request_limit']==2 and me['auto_approve_requests']
 uid2,user2=new_user('race@example.com');assert request(admin,'/api/v1/users/'+uid2+'/request-policy',{'monthly_request_limit':1,'auto_approve_requests':False},'PUT')[0]==200
 def submit(mid):return request(login('race@example.com'),'/api/v1/movies/requests',payload(mid),'POST')
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(submit,movies[2:6]))
 assert sorted(s for s,_ in results)==[201,429,429,429],[(s,str(d)[:100]) for s,d in results]
 assert next(d for s,d in results if s==201)['authorized'] is False
 assert request(user2,'/api/v1/requests/quota')[1]['used']==1
 # Old-month ledger records stop counting; deletion did not erase them.
 exec_python("from sqlalchemy import text;from media_manager.config import MediaManagerConfig;from media_manager.database import init_engine;e=init_engine(MediaManagerConfig().database);c=e.connect();c.execute(text(\"UPDATE request_usage SET created_at=created_at-interval '62 days' WHERE user_id=:id\"),{'id':"+repr(uid)+"});c.commit()")
 assert request(user,'/api/v1/requests/quota')[1]['used']==0
 assert request(user,'/api/v1/movies/requests',payload(movies[6]),'POST')[0]==201
 assert request(user,'/api/v1/requests/quota')[1]['used']==1
 secrets_before=[(root/'state/secrets'/n).read_bytes() for n in ['app_db_password','db_admin_password']]
 stack('down');subprocess.run(command,env=env,stdout=subprocess.DEVNULL,check=True)
 for _ in range(90):
  try:
   if request(admin,'/api/v1/health')[0]==200:break
  except Exception:pass
  time.sleep(1)
 assert secrets_before==[(root/'state/secrets'/n).read_bytes() for n in ['app_db_password','db_admin_password']]
 user=login('user@example.com');assert request(user,'/api/v1/requests/quota')[1]['used']==1
 assert not (root/'state/config/initial-admin.json').exists()
 print(json.dumps({'managed_database_provisioning':'passed','least_privilege':'passed','monthly_combined_quota':'passed','auto_approval':'passed','manual_approval':'passed','deletion_no_refund':'passed','self_escalation_blocked':'passed','concurrent_requests':'one accepted, three blocked','month_reset':'passed','restart_and_secret_persistence':'passed','admin_user_creation_and_login':'passed','duplicate_email_rejected':'passed','creation_admin_only':'passed','catalogue_without_file_changes':'passed','reorganize_explicit_mode':'passed','partial_season_and_missing_files':'passed','import_validation':'passed','production_data_used':False}))
except Exception:
 try:
  log=stack('logs','--no-color');
  for value in [password,*(p.read_text() for p in (root/'state/secrets').glob('*') if p.is_file())]:log=log.replace(value,'[redacted]')
  (root/'failure.log').write_text(log);(root/'failure.log').chmod(0o600)
  print('Private test logs:',root/'failure.log')
 except Exception:pass
 raise
finally:
 if os.getenv('MM_TEST_KEEP')!='1' or (root/'failure.log').exists():
  try:stack('down','--remove-orphans')
  except Exception:pass
 if os.getenv('MM_TEST_KEEP')=='1' and not (root/'failure.log').exists():
  access=root/'test-access.json';access.write_text(json.dumps({'base':base,'password':password,'project':project,'state':str(root/'state')}));access.chmod(0o600);print('Kept test stack:',str(access))
 elif not (root/'failure.log').exists():shutil.rmtree(root)
