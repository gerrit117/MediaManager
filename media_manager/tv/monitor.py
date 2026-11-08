"""Persistent episode monitoring. Network ambiguity never causes an automatic resubmission."""
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.library import video_files, episode_numbers
from media_manager.release_policy import allowed_results, rank
from media_manager.torrent.models import Torrent
from media_manager.tv.models import Show, EpisodeDownload, SeasonFile as FileModel
from media_manager.tv.schemas import SeasonFile

log=logging.getLogger(__name__)

def present_episodes(service, show, season):
    paths=video_files(service.get_root_season_directory(show,season.number))
    for record in service.tv_repository.get_season_files_by_season_id(season.id):
        paths.extend(p for p in (record.source_files or []) if Path(p).is_file())
    return episode_numbers(paths,season.number)

def claimed_episodes(service, season):
    """Include existing manual/season-pack downloads, including unknown/error states."""
    claimed=set()
    for record in service.tv_repository.get_season_files_by_season_id(season.id):
        if record.torrent_id is None:continue
        torrent=service.torrent_service.torrent_repository.get_torrent_by_id(record.torrent_id)
        if torrent.imported:continue
        if record.episode_numbers:claimed.update(record.episode_numbers)
        else:
            specific=episode_numbers([torrent.title],season.number)
            if specific:claimed.update(specific)
            else:claimed.update(e.number for e in season.episodes)
    return claimed

def should_search(episode, since, today, present, claimed, previous):
    if episode.air_date is None or not since <= episode.air_date <= today:return False
    if episode.number in claimed:return False
    if previous is not None and previous.status != 'imported':return False
    return episode.number not in present or previous is not None

def run_show(service, show):
    db=service.tv_repository.db
    current=datetime.now(ZoneInfo('Europe/Berlin'))
    row=db.get(Show,show.id)
    if not row.continuous_download:return
    if row.monitor_from is None:
        row.monitor_from=current.date();db.commit()
    since=row.monitor_from
    # Refresh airing dates every six hours, independently of the weekly library refresh.
    if row.monitor_checked_at is None or current-row.monitor_checked_at > timedelta(hours=6):
        from media_manager.metadataProvider.tmdb import TmdbMetadataProvider
        from media_manager.metadataProvider.tvdb import TvdbMetadataProvider
        provider=TmdbMetadataProvider() if show.metadata_provider=='tmdb' else TvdbMetadataProvider()
        updated=service.update_show_metadata(show,provider)
        if updated is None:return
        show=updated
        row=db.get(Show,show.id);row.monitor_checked_at=current;db.commit()
    for season in show.seasons:
        if season.number<=0 or not any(e.air_date is not None and since<=e.air_date<=current.date() for e in season.episodes):continue
        season_results=None
        present=present_episodes(service,show,season)
        claimed=claimed_episodes(service,season)
        for episode in season.episodes:
            from media_manager.release_control import locked
            if episode.number in present and locked(db,'episode',episode.id):continue
            previous=db.get(EpisodeDownload,episode.id)
            if not should_search(episode,since,current.date(),present,claimed,previous):continue
            if previous is not None and previous.checked_at is not None and current-previous.checked_at < timedelta(hours=6):continue
            if previous is not None:
                previous.checked_at=current;db.commit()
            # The existing indexer adapter handles ID-based lookups, categories and both protocols.
            if season_results is None:
                season_results=service.get_all_available_torrents_for_a_season(season.number,show.id)
            results=allowed_results([r for r in season_results if r.season==[season.number]
                and episode_numbers([r.title],season.number)=={episode.number}],available_only=True)
            if not results:continue
            best=results[0]
            if previous is not None:
                old=IndexerQueryResult(title=previous.release_title,download_url='',seeders=3,flags=[],size=0,usenet=True,age=0,indexer=None)
                if rank(best)[:2] <= rank(old)[:2]:continue
                previous.status='submitting';previous.release_title=best.title;previous.error=None;db.commit()
            else:
                added=db.execute(insert(EpisodeDownload).values(episode_id=episode.id,status='submitting',release_title=best.title,checked_at=current)
                    .on_conflict_do_nothing(index_elements=['episode_id']).returning(EpisodeDownload.episode_id)).scalar_one_or_none()
                db.commit()
                if added is None:continue
            job=db.get(EpisodeDownload,episode.id)
            try:
                from media_manager.release_control import automatic_manifest,attach
                manifest=automatic_manifest(service,'show',show,season,episode)
                torrent=service.torrent_service.download(best)
                job.torrent_id=torrent.id
                suffix=f'AUTO-S{season.number:02d}E{episode.number:02d}-'+hashlib.sha256(best.title.encode()).hexdigest()[:12]
                record=SeasonFile(season_id=season.id,torrent_id=torrent.id,quality=best.quality,
                    file_path_suffix=suffix,episode_numbers=[episode.number])
                service.tv_repository.add_season_file(record)
                attach(db,torrent.id,'show',show.id,manifest)
                job.status='submitted';db.commit();claimed.add(episode.number)
            except Exception as error:
                db.rollback();job=db.get(EpisodeDownload,episode.id)
                job.status='uncertain';job.error='Submission could not be confirmed; inspect the downloader before retrying.';db.commit()
                log.error('Episode download could not be confirmed for %s S%02dE%02d (%s)',show.name,season.number,episode.number,type(error).__name__)

def monitor_new_episodes():
    from media_manager.database import get_session
    from media_manager.tv.repository import TvRepository
    from media_manager.tv.service import TvService
    from media_manager.torrent.repository import TorrentRepository
    from media_manager.torrent.service import TorrentService
    from media_manager.indexer.repository import IndexerRepository
    from media_manager.indexer.service import IndexerService
    from media_manager.notification.repository import NotificationRepository
    from media_manager.notification.service import NotificationService
    with next(get_session()) as db:
        # Separate session-level PostgreSQL lock survives the repository's intermediate commits.
        with db.get_bind().connect() as lock:
            if not lock.scalar(text('SELECT pg_try_advisory_lock(194731, 501)')):return
            try:
                service=TvService(TvRepository(db),TorrentService(TorrentRepository(db)),IndexerService(IndexerRepository(db)),NotificationService(NotificationRepository(db)))
                for show in service.tv_repository.get_shows():
                    if not show.continuous_download:continue
                    try:run_show(service,show)
                    except Exception:
                        db.rollback();log.exception('Episode monitoring failed for show %s',show.id)
            finally:lock.execute(text('SELECT pg_advisory_unlock(194731, 501)'))
