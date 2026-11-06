"""First-run wizard, served before the normal application or DB migrations."""
import hmac
import json
import os
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from media_manager.configuration import config_file, atomic_json

class SetupInput(BaseModel):
    code: str
    database_host: str = ''
    database_port: int = Field(default=5432,ge=1,le=65535)
    database_name: str = ''
    database_user: str = ''
    database_password: str = ''
    movie_directory: str = '/data/movies'
    tv_directory: str = '/data/tv'
    download_directory: str = '/downloads'
    admin_email: str
    admin_password: str = Field(min_length=12)


def render_html(language='de') -> str:
    fields = [('code','Einrichtungscode (aus setup-code)','password'),('database_host','PostgreSQL-Host','text'),('database_port','PostgreSQL-Port','number'),('database_name','Datenbankname','text'),('database_user','Datenbankbenutzer','text'),('database_password','Datenbankpasswort','password'),('movie_directory','Filmpfad im Container','text'),('tv_directory','Serienpfad im Container','text'),('download_directory','Downloadpfad im Container','text'),('admin_email','Admin-E-Mail','email'),('admin_password','Admin-Passwort (mindestens 12 Zeichen)','password')]
    defaults={'database_port':'5432','movie_directory':'/data/movies','tv_directory':'/data/tv','download_directory':'/downloads'}
    if os.getenv('MEDIAMANAGER_MANAGED_DATABASE') == 'true':
        fields=[f for f in fields if not f[0].startswith('database_')]
    inputs=''.join(f'<label>{label}<input required name="{key}" type="{kind}" value="{defaults.get(key, "")}" {"minlength=12" if key=="admin_password" else ""}></label>' for key,label,kind in fields)
    html = '''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MediaManager einrichten</title><style>body{font:16px system-ui;background:#101416;color:#edf4f3;margin:0;padding:24px}main{max-width:720px;margin:auto}form{display:grid;gap:18px}label{display:grid;gap:8px}input,button{font:inherit;padding:12px;border-radius:10px;background:#202a2c;color:inherit;border:1px solid #465453;min-width:0}button{background:#247c6b}p{line-height:1.5}#message{white-space:pre-wrap}</style><main><h1>Willkommen bei MediaManager</h1><p>PostgreSQL und die Bibliothek verbinden, danach mit deinem neuen Administratorkonto anmelden. Indexer und Downloadmanager richtest du anschließend unter Einstellungen ein.</p><p>Der private Einrichtungscode liegt im Konfigurationsordner in <code>setup-code</code>. Es werden keine vorhandenen Konfigurationen überschrieben. Der verwaltete Stack richtet PostgreSQL automatisch ein. Bei einer externen Datenbank benötigst du deren Zugangsdaten.</p><form id="form">'''+inputs+'''<button>Prüfen & Einrichtung abschließen</button></form><p role="status" id="message"></p><script>const form=document.querySelector('form'),message=document.querySelector('#message');form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;const data=Object.fromEntries(new FormData(form));data.database_port=Number(data.database_port);try{const response=await fetch('/setup/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!response.ok)throw Error((await response.json()).detail||'Einrichtung fehlgeschlagen');message.textContent='Einrichtung gespeichert. MediaManager startet jetzt. Gleich kannst du dich anmelden.';form.remove();setInterval(async()=>{try{const health=await fetch('/api/v1/health');if(health.ok&&health.headers.get('content-type')?.includes('application/json'))location.href='/web/login/?next=/web/dashboard/settings/';}catch{}},3000);}catch(error){message.textContent=error.message;button.disabled=false;}};</script></main></html>'''

    chooser = f"""<label>Language / Sprache<select onchange="location.search='?lang='+this.value"><option value="de" {'selected' if language=='de' else ''}>Deutsch</option><option value="en" {'selected' if language=='en' else ''}>English</option></select></label>"""
    html=html.replace('<main>','<main>'+chooser,1)
    html=html.replace('<script>',"<script>localStorage.setItem('mediamanager-language',"+json.dumps(language)+");document.cookie='mm_language='+"+json.dumps(language)+"+';path=/;SameSite=Lax';",1)
    if language=='en':
        pairs={
          'Willkommen bei MediaManager':'Welcome to MediaManager',
          'MediaManager einrichten':'Set up MediaManager',
          'Einrichtungscode (aus setup-code)':'Setup code (from setup-code)',
          'PostgreSQL-Host':'PostgreSQL host','PostgreSQL-Port':'PostgreSQL port',
          'Datenbankname':'Database name','Datenbankbenutzer':'Database username','Datenbankpasswort':'Database password',
          'Filmpfad im Container':'Movie directory inside container','Serienpfad im Container':'TV directory inside container','Downloadpfad im Container':'Download directory inside container',
          'Admin-E-Mail':'Administrator email','Admin-Passwort (mindestens 12 Zeichen)':'Administrator password (at least 12 characters)',
          'PostgreSQL und die Bibliothek verbinden, danach mit deinem neuen Administratorkonto anmelden. Indexer und Downloadmanager richtest du anschließend unter Einstellungen ein.':'Connect PostgreSQL and your library, then sign in with your new administrator account. Configure indexers and download managers in Settings afterwards.',
          'Der private Einrichtungscode liegt im Konfigurationsordner in':'The private setup code is in the configuration directory in',
          'Es werden keine vorhandenen Konfigurationen überschrieben.':'Existing configurations are never overwritten.',
          'Der verwaltete Stack richtet PostgreSQL automatisch ein. Bei einer externen Datenbank benötigst du deren Zugangsdaten.':'The managed stack provisions PostgreSQL automatically. An external database requires its own credentials.',
          'Prüfen & Einrichtung abschließen':'Verify & finish setup',
          'Einrichtung gespeichert. MediaManager startet jetzt. Gleich kannst du dich anmelden.':'Setup saved. MediaManager is starting. You can sign in shortly.',
          'Einrichtung fehlgeschlagen':'Setup failed',
        }
        for source,target in sorted(pairs.items(),key=lambda item:-len(item[0])):html=html.replace(source,target)
        html=html.replace('lang="de"','lang="en"',1)
    return html



def create_setup_app(stop=lambda:None) -> FastAPI:
    config = config_file()
    config.parent.mkdir(parents=True,exist_ok=True)
    code_file=config.parent/'setup-code'
    if not code_file.exists():
        code_file.write_text(os.getenv('MEDIAMANAGER_SETUP_CODE') or secrets.token_urlsafe(24));code_file.chmod(0o600)
    app=FastAPI()
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from media_manager.api_language import http_error
    app.add_exception_handler(StarletteHTTPException,http_error)

    @app.get('/{path:path}',response_class=HTMLResponse)
    def index(path:str,request:Request):
        language=request.query_params.get('lang') or ('de' if request.headers.get('accept-language','de').startswith('de') else 'en')
        return render_html(language if language in ('de','en') else 'en')

    @app.post('/setup/complete')
    def complete(body:SetupInput,tasks:BackgroundTasks):
        if config.exists(): raise HTTPException(409,'Bereits eingerichtet')
        if not hmac.compare_digest(body.code,code_file.read_text().strip()): raise HTTPException(403,'Einrichtungscode ist falsch')
        if os.getenv('MEDIAMANAGER_MANAGED_DATABASE') == 'true':
            body.database_host=os.getenv('MEDIAMANAGER_DB_HOST','database')
            body.database_port=5432
            body.database_name='mediamanager';body.database_user='mediamanager'
            try:body.database_password=Path(os.environ['MEDIAMANAGER_DB_PASSWORD_FILE']).read_text().strip()
            except (OSError,KeyError):raise HTTPException(503,'Automatisch erzeugte Datenbankzugangsdaten fehlen') from None
        if not all([body.database_host,body.database_name,body.database_user,body.database_password]):raise HTTPException(400,'Datenbankverbindung ist unvollständig')
        from media_manager.auth.schemas import UserCreate
        try: UserCreate(email=body.admin_email,password=body.admin_password)
        except Exception: raise HTTPException(400,'Admin-E-Mail oder Passwort ungültig') from None
        for folder in (body.movie_directory,body.tv_directory,body.download_directory):
            p=Path(folder)
            if not p.is_absolute(): raise HTTPException(400,'Containerpfade müssen absolut sein')
            try:
                p.mkdir(parents=True,exist_ok=True)
                import tempfile
                with tempfile.TemporaryFile(dir=p):pass
            except OSError: raise HTTPException(400,'Bibliotheks- oder Downloadpfad nicht schreibbar; UID/GID und Mounts prüfen') from None
        try:
            import psycopg
            with psycopg.connect(host=body.database_host,port=body.database_port,dbname=body.database_name,user=body.database_user,password=body.database_password,connect_timeout=5) as connection:
                connection.execute('SELECT 1')
                exists=connection.execute("SELECT to_regclass('public.user')").fetchone()[0]
                if exists and connection.execute('SELECT count(*) FROM "user"').fetchone()[0]:
                    raise HTTPException(409,'Datenbank enthält bereits Benutzer. Bestehende Konfiguration verwenden; kein neues Administratorkonto wird angelegt.')
        except HTTPException:raise
        except Exception:raise HTTPException(400,'PostgreSQL nicht erreichbar oder Zugangsdaten ungültig') from None
        data={'database':{'host':body.database_host,'port':body.database_port,'dbname':body.database_name,'user':body.database_user,'password':body.database_password},'misc':{'movie_directory':body.movie_directory,'tv_directory':body.tv_directory,'torrent_directory':body.download_directory,'image_directory':'/data/images'},'auth':{'token_secret':secrets.token_hex(32),'admin_emails':[body.admin_email]},'metadata':{'tmdb':{'default_language':'de','primary_languages':['de','en']}}}
        # The generated initial TOML contains only scalar/list values; strings are JSON-escaped.
        lines=[]
        def table(prefix,values):
            scalars={k:v for k,v in values.items() if not isinstance(v,dict)}
            if scalars:
                lines.append('['+prefix+']')
                lines.extend(k+' = '+json.dumps(v,ensure_ascii=True) for k,v in scalars.items())
                lines.append('')
            for key,value in values.items():
                if isinstance(value,dict):table(prefix+'.'+key if prefix else key,value)
        table('',data)
        atomic_json(config.parent/'initial-admin.json',{'email':body.admin_email,'password':body.admin_password})
        # Exclusive creation prevents overwriting a configuration supplied concurrently.
        try:
            descriptor=os.open(config,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:raise HTTPException(409,'Konfiguration wurde inzwischen angelegt') from None
        with os.fdopen(descriptor,'w') as stream:stream.write('\n'.join(lines));stream.flush();os.fsync(stream.fileno())
        atomic_json(config.parent/'connections-setup.json',{'pending':True})
        tasks.add_task(stop)
        return {'saved':True}
    return app


def run():
    import uvicorn
    config=uvicorn.Config(create_setup_app(lambda:setattr(server,'should_exit',True)),host='0.0.0.0',port=int(os.getenv('PORT','8000')),access_log=False)
    server=uvicorn.Server(config)
    server.run()

if __name__=='__main__':
    if not config_file().exists():run()
    from media_manager.configuration import activate_settings
    activate_settings()
