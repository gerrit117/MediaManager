#!/usr/bin/env python3
"""Provision a separate managed stack. Never mounts the host Docker socket in the app."""
import argparse,os,secrets,subprocess,shutil
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--directory',type=Path,required=True)
parser.add_argument('--movies',type=Path,required=True)
parser.add_argument('--tv',type=Path,required=True)
parser.add_argument('--downloads',type=Path,required=True)
parser.add_argument('--port',type=int,default=8095)
parser.add_argument('--uid',type=int,default=99)
parser.add_argument('--gid',type=int,default=100)
parser.add_argument('--with-nzb',action='store_true')
parser.add_argument('--with-torrent',action='store_true')
parser.add_argument('--compose-binary',type=Path)
parser.add_argument('--project-name',default='mediamanager-managed')
parser.add_argument('--prepare-only',action='store_true')
args=parser.parse_args()
root=args.directory.resolve();root.mkdir(parents=True,exist_ok=True)
if (root/'config/config.toml').exists() and not (root/'stack.env').exists():raise SystemExit('Existing unmanaged configuration found; choose a separate directory')
if (root/'postgres/PG_VERSION').exists() and any(not (root/'secrets'/n).exists() for n in ['app_db_password','db_admin_password']):raise SystemExit('Restore missing database secrets from backup; passwords will not be regenerated for existing data')
# A managed stack uses its own DB directory and credentials; no existing service is adopted.
for name in ['config','postgres','images','sabnzbd','qbittorrent','secrets']:
 p=root/name;p.mkdir(exist_ok=True)
 if os.geteuid()==0:os.chown(p,args.uid,args.gid)
 p.chmod(0o700)
for name in ['db_admin_password','app_db_password']:
 p=root/'secrets'/name
 if not p.exists():
  fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'w') as stream:stream.write(secrets.token_hex(32))
 if os.geteuid()==0:os.chown(p,args.uid,args.gid)
 p.chmod(0o600)
values={'MM_STATE':str(root),'MM_MOVIES':str(args.movies.resolve()),'MM_TV':str(args.tv.resolve()),'MM_DOWNLOADS':str(args.downloads.resolve()),'MM_UID':str(args.uid),'MM_GID':str(args.gid),'MM_PORT':str(args.port),'COMPOSE_PROJECT_NAME':args.project_name}
for key in ['MM_MOVIES','MM_TV','MM_DOWNLOADS']:
 p=Path(values[key])
 if not p.is_dir():raise SystemExit('Media/download directories must already exist: '+str(p))
envfile=root/'stack.env'
# Paths with special interpolation characters need explicit configuration rather than shell evaluation.
if any(any(c in v for c in '\n\r$') for v in values.values()):raise SystemExit('Unsupported character in path')
fd=os.open(envfile,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as stream:stream.write(''.join(k+'='+v+'\n' for k,v in values.items()))
if not args.prepare_only:
 command=([str(args.compose_binary)] if args.compose_binary else [shutil.which('docker-compose')] if shutil.which('docker-compose') else ['docker','compose'])+['--env-file',str(envfile),'-f',str(Path(__file__).resolve().parents[1]/'compose.managed.yaml')]
 for enabled,profile in [(args.with_nzb,'nzb'),(args.with_torrent,'torrent')]:
  if enabled:command+=['--profile',profile]
 subprocess.run(command+['up','-d'],check=True)
print('Managed stack prepared. Open the configured HTTP port; read the private setup-code in the config directory for first-run access.')
