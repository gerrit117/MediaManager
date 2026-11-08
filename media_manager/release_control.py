"""Explicit replacement: stage the new version first, retain originals in an archive."""
import os,json,shutil,logging,subprocess
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from fastapi import HTTPException
from media_manager.config import MediaManagerConfig
from media_manager.media_features_models import ReleaseLock,Replacement
from media_manager.library import video_files,episode_numbers
from media_manager.tv.models import Episode,Season
log=logging.getLogger(__name__)

def locked(db,kind,media_id):
    if db.get(ReleaseLock,(kind,media_id)):return True
    if kind=='episode':
        ep=db.get(Episode,media_id)
        return bool(ep and locked(db,'season',ep.season_id))
    if kind=='season':
        season=db.get(Season,media_id)
        return bool(season and locked(db,'show',season.show_id))
    return False

def roots():
    c=MediaManagerConfig().misc
    return [Path(p).resolve() for p in [c.movie_directory,c.tv_directory,*[x.path for x in c.movie_libraries],*[x.path for x in c.tv_libraries]]]

def permitted(path):
    p=Path(path)
    if p.is_symlink():raise ValueError('Symlinked media cannot be replaced automatically.')
    resolved=p.resolve()
    if not any(resolved.is_relative_to(root) and resolved!=root for root in roots()):raise ValueError('Replacement is outside a configured media library.')
    if any(part.startswith('.mediamanager-') for part in resolved.parts):raise ValueError('Archived media cannot be selected for replacement.')
    return resolved

def fingerprint(p):
    st=p.stat();return {'path':str(p),'size':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}

def plan(db,kind,media_id,paths,replace_existing,override_lock,scopes):
    found={}
    for source in paths:
        p=permitted(source)
        if p.is_file():
            found[str(p)]=fingerprint(p)
            for sibling in p.parent.glob(p.stem+'*'):
                if sibling.suffix.lower() in ('.srt','.ass','.ssa','.sub','.idx') and (sibling.stem==p.stem or sibling.stem.startswith(p.stem+'.')):
                    companion=permitted(sibling);found[str(companion)]=fingerprint(companion)
    if found and any(locked(db,k,i) for k,i in scopes) and not override_lock:
        raise HTTPException(409,'This release is protected. Confirm the manual override to continue.')
    if not replace_existing:return None
    return {'old_files':list(found.values()),'archived_files':[]}

def attach(db,job_id,kind,media_id,manifest):
    if manifest is not None:
        db.add(Replacement(job_id=job_id,kind=kind,media_id=media_id,manifest=manifest,status='pending'));db.commit()

def verified_video(path):
    p=permitted(path)
    if not p.is_file() or p.stat().st_size<=0:return False
    result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_type','-of','json',str(p)],capture_output=True,timeout=30)
    if result.returncode:return False
    return bool(json.loads(result.stdout).get('streams'))

def finalize(db,job_id,new_paths):
    row=db.get(Replacement,job_id)
    if row is None or row.status=='completed':return
    new_paths={str(permitted(p)) for p in new_paths}
    if not new_paths or not all(verified_video(p) for p in new_paths):
        row.status='validation_failed';db.commit();raise ValueError('Replacement media validation failed; original files were retained.')
    manifest=dict(row.manifest);archived=list(manifest.get('archived_files',[]))
    try:
        for old in manifest['old_files']:
            p=permitted(old['path'])
            if str(p) in new_paths:raise ValueError('New release must use a separate staging filename.')
            if not p.exists():
                if any(x['source']==str(p) for x in archived):continue
                raise ValueError('Original media changed after the replacement was scheduled.')
            if fingerprint(p)!=old:raise ValueError('Original media changed after the replacement was scheduled.')
            root=max((r for r in roots() if p.is_relative_to(r)),key=lambda r:len(r.parts))
            archive_root=root/'.mediamanager-replaced'
            archive_root.mkdir(parents=True,exist_ok=True)
            (archive_root/'.ignore').touch(exist_ok=True)
            if not (archive_root/'.embyignore').exists():(archive_root/'.embyignore').write_text('*\n')
            target=archive_root/str(job_id)/p.relative_to(root)
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise ValueError('Replacement archive target already exists.')
            # Persist the intended move first: restart can reconcile a completed rename.
            archived.append({'source':str(p),'archive':str(target)})
            manifest['archived_files']=archived;row.manifest=dict(manifest);db.commit()
            os.rename(p,target)
        row.status='completed';row.manifest=manifest;db.commit()
    except Exception:
        # Restore moved originals on failure; never delete either copy.
        for item in reversed(archived):
            source=Path(item['source']);archive=Path(item['archive'])
            if archive.is_file() and not source.exists():os.rename(archive,source)
        row.status='failed';manifest['archived_files']=[];row.manifest=manifest;db.commit();raise

def run_pending_replacements():
    from media_manager.database import get_session
    from media_manager.torrent.models import Torrent
    from media_manager.movies.models import MovieFile
    from media_manager.tv.models import SeasonFile
    # Import completion calls finalize directly; retry incomplete manifests after restart.
    with next(get_session()) as db:
        for row in db.scalars(select(Replacement).where(Replacement.status=='pending')):
            job=db.get(Torrent,row.job_id)
            if not job or not job.imported:continue
            files=list(db.scalars(select(MovieFile).where(MovieFile.torrent_id==job.id))) if row.kind=='movie' else list(db.scalars(select(SeasonFile).where(SeasonFile.torrent_id==job.id)))
            paths=[p for f in files for p in (f.source_files or [])]
            try:finalize(db,job.id,paths)
            except Exception:log.warning('Replacement validation failed for job %s; originals retained.',job.id)

def automatic_manifest(service,kind,media,season=None,episode=None):
    from media_manager.movies.models import MovieFile
    from media_manager.tv.models import SeasonFile
    if kind=='movie':
        db=service.movie_repository.db;paths=video_files(service.get_movie_root_path(media))
        for row in db.scalars(select(MovieFile).where(MovieFile.movie_id==media.id)):paths.extend(row.source_files or [])
        return plan(db,'movie',media.id,paths,True,False,[('movie',media.id)])
    db=service.tv_repository.db;paths=video_files(service.get_root_season_directory(media,season.number))
    for row in db.scalars(select(SeasonFile).where(SeasonFile.season_id==season.id)):paths.extend(row.source_files or [])
    if episode:
        for p in paths:
            coverage=episode_numbers([p],season.number)
            if episode.number in coverage and coverage!={episode.number}:raise ValueError('An existing file covers additional episodes; automatic partial replacement is unsafe.')
        paths=[p for p in paths if episode.number in episode_numbers([p],season.number)]
        scopes=[('episode',episode.id)]
    else:scopes=[('season',season.id)]+[('episode',ep.id) for ep in season.episodes]
    return plan(db,'show',media.id,paths,True,False,scopes)
