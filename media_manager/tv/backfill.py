"""Opt-in downloads for aired episodes missing from a series."""
import fcntl
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from media_manager.configuration import atomic_json, config_file
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.library import episode_numbers
from media_manager.library_availability import season_presence
from media_manager.release_policy import allowed_results, rank
from media_manager.tv.models import EpisodeDownload
from media_manager.tv.monitor import claimed_episodes
from media_manager.tv.schemas import Season, SeasonFile, Show, ShowId

if TYPE_CHECKING:
    from media_manager.tv.service import TvService

log = logging.getLogger(__name__)


@dataclass
class ReleaseChoice:
    release: IndexerQueryResult
    episodes: set[int]


def select_releases(
    season: Season,
    missing: set[int],
    results: list[IndexerQueryResult],
    *,
    allow_pack: bool,
) -> list[ReleaseChoice]:
    """Choose non-overlapping releases, preserving language and resolution priority."""
    singles: dict[int, IndexerQueryResult] = {}
    pack = None
    for release in allowed_results(results, available_only=True):
        if release.season != [season.number]:
            continue
        episodes = episode_numbers([release.title], season.number)
        if not episodes and allow_pack and pack is None:
            # A season marker followed by an episode marker is never a pack.
            if not re.search(r"(?i)\bs\d+[ ._-]*e\d", release.title):
                pack = release
        elif len(episodes) == 1 and episodes <= missing:
            singles.setdefault(next(iter(episodes)), release)

    choices = []
    if pack is not None:
        pack_priority = rank(pack)[:2]
        covered = {
            number for number in missing
            if number not in singles or pack_priority >= rank(singles[number])[:2]
        }
        if covered:
            choices.append(ReleaseChoice(pack, covered))
            for number in covered:
                singles.pop(number, None)
    choices.extend(ReleaseChoice(release, {number}) for number, release in sorted(singles.items()))
    return choices


def missing_episodes(service: "TvService", show: Show, season: Season, today: date) -> set[int]:
    db = service.tv_repository.db
    episode_ids = {episode.id: episode.number for episode in season.episodes}
    if not episode_ids:
        return set()
    reserved = {
        episode_ids[job.episode_id]
        for job in db.scalars(select(EpisodeDownload).where(
            EpisodeDownload.episode_id.in_(episode_ids),
            EpisodeDownload.status != "imported",
        ))
    }
    aired = {
        episode.number for episode in season.episodes
        if episode.air_date is not None and episode.air_date <= today
    }
    return aired - season_presence(service, show, season) - claimed_episodes(service, season) - reserved


def find_releases(
    service: "TvService", show: Show, season: Season, missing: set[int], *, allow_pack: bool = True,
) -> list[ReleaseChoice]:
    from media_manager.config import MediaManagerConfig

    manager = service.torrent_service.download_manager
    policy = MediaManagerConfig().indexers.release_policy
    if not service.indexer_service.indexers:
        raise HTTPException(409, "Configure an indexer before searching for missing episodes.")

    def usable(results):
        return allowed_results(
            [result for result in results if manager.supports_download(result)],
            available_only=True,
        )

    if len(missing) == 1 and not allow_pack:
        number = next(iter(missing))
        query = f"{show.name} S{season.number:02d}E{number:02d}"
        results = usable(service.get_all_available_torrents_for_a_season(
            season.number, show.id, search_query_override=query,
        ))
        return select_releases(season, missing, results, allow_pack=False)

    results = usable(service.get_all_available_torrents_for_a_season(season.number, show.id))
    best_priority = (len(policy.languages), len(policy.resolutions)) if policy.enabled else (0, -1)
    allow_pack = allow_pack and missing == {episode.number for episode in season.episodes}
    initial = select_releases(season, missing, results, allow_pack=allow_pack)
    if initial and initial[0].episodes == missing and rank(initial[0].release)[:2] == best_priority:
        return initial

    singles = select_releases(season, missing, results, allow_pack=False)
    best_by_episode = {next(iter(choice.episodes)): choice.release for choice in singles}
    for number in sorted(missing):
        current = best_by_episode.get(number)
        if current is not None and rank(current)[:2] == best_priority:
            continue
        query = f"{show.name} S{season.number:02d}E{number:02d}"
        targeted = service.get_all_available_torrents_for_a_season(
            season.number, show.id, search_query_override=query,
        )
        results.extend(
            release for release in usable(targeted)
            if episode_numbers([release.title], season.number) == {number}
        )
    return select_releases(season, missing, results, allow_pack=allow_pack)


def submit(service: "TvService", season: Season, choice: ReleaseChoice) -> bool:
    """Reserve every covered episode before contacting the download manager."""
    db = service.tv_repository.db
    episode_ids = [episode.id for episode in season.episodes if episode.number in choice.episodes]
    values = {
        "status": "submitting",
        "release_title": choice.release.title,
        "checked_at": datetime.now(timezone.utc),
        "torrent_id": None,
        "error": None,
    }
    reservation = insert(EpisodeDownload).values([
        dict(values, episode_id=episode_id) for episode_id in sorted(episode_ids)
    ])
    reserved = db.scalars(reservation.on_conflict_do_update(
        index_elements=["episode_id"], set_=values, where=EpisodeDownload.status == "imported",
    ).returning(EpisodeDownload.episode_id)).all()
    if len(reserved) != len(episode_ids):
        db.rollback()
        return False
    db.commit()

    torrent = None
    try:
        torrent = service.torrent_service.download(choice.release)
        service.tv_repository.add_season_file(SeasonFile(
            season_id=season.id,
            torrent_id=torrent.id,
            quality=choice.release.quality,
            file_path_suffix=f"AUTO-{torrent.id}",
            episode_numbers=sorted(choice.episodes),
        ))
        for episode_id in episode_ids:
            job = db.get(EpisodeDownload, episode_id)
            job.torrent_id = torrent.id
            job.status = "submitted"
        db.commit()
    except Exception:
        db.rollback()
        for episode_id in episode_ids:
            job = db.get(EpisodeDownload, episode_id)
            if torrent is not None:
                job.torrent_id = torrent.id
            job.status = "uncertain"
            job.error = "Submission could not be confirmed; inspect the downloader before retrying."
        db.commit()
        # Downloader exceptions can include a URL containing an indexer credential.
        log.error("Backfill submission could not be confirmed for season %s", season.id)
        raise HTTPException(502, "Submission could not be confirmed. Check Downloads before retrying.") from None
    return True


def _path(show_id: ShowId, suffix: str) -> Path:
    directory = config_file().parent / "episode-backfills"
    return directory / f"{show_id}.{suffix}"


def _lease(show_id: ShowId) -> BinaryIO:
    lock_path = _path(show_id, "lock")
    lock_path.parent.mkdir(exist_ok=True)
    lease = lock_path.open("ab")
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise HTTPException(409, "A missing episode search is already running.") from None
    return lease


def _read(show_id: ShowId) -> dict:
    try:
        return json.loads(_path(show_id, "json").read_text())
    except FileNotFoundError:
        return {"status": "idle"}


def status(show_id: ShowId) -> dict:
    result = _read(show_id)
    if result["status"] == "running":
        try:
            with _lease(show_id):
                result = _read(show_id)
                if result["status"] == "running":
                    result["status"] = "interrupted"
                    atomic_json(_path(show_id, "json"), result)
        except HTTPException:
            pass
    return result


def start(
    show_id: ShowId, season_number: int | None, tasks: BackgroundTasks,
    episode_number: int | None = None,
) -> None:
    lease, report = _begin(show_id, season_number, episode_number)
    try:
        tasks.add_task(run, show_id, season_number, episode_number, lease, report)
    except BaseException:
        lease.close()
        raise


def _begin(show_id: ShowId, season_number: int | None, episode_number: int | None) -> tuple[BinaryIO, dict]:
    lease = _lease(show_id)
    report = {
        "status": "running", "season_number": season_number, "episode_number": episode_number,
        "current_season": None, "started_at": datetime.now(timezone.utc).isoformat(),
        "queued_downloads": 0, "queued_episodes": 0, "not_found": [], "errors": [],
    }
    try:
        atomic_json(_path(show_id, "json"), report)
    except BaseException:
        lease.close()
        raise
    return lease, report


def run_history(show_id: ShowId) -> None:
    """Retry older missing episodes at most once per six hours."""
    previous = status(show_id)
    if previous["status"] == "running":
        return
    started_at = previous.get("started_at")
    if previous.get("season_number") is None and started_at:
        if datetime.now(timezone.utc) - datetime.fromisoformat(started_at) < timedelta(hours=6):
            return
    try:
        lease, report = _begin(show_id, None, None)
    except HTTPException:
        return
    run(show_id, None, None, lease, report)


def run(
    show_id: ShowId, season_number: int | None, episode_number: int | None,
    lease: BinaryIO, report: dict,
) -> None:
    from sqlalchemy.orm import Session

    from media_manager.database import get_engine
    from media_manager.indexer.repository import IndexerRepository
    from media_manager.indexer.service import IndexerService
    from media_manager.notification.repository import NotificationRepository
    from media_manager.notification.service import NotificationService
    from media_manager.torrent.repository import TorrentRepository
    from media_manager.torrent.service import TorrentService
    from media_manager.tv.repository import TvRepository
    from media_manager.tv.service import TvService

    path = _path(show_id, "json")
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    with lease:
        try:
            with Session(get_engine()) as db:
                service = TvService(
                    TvRepository(db), TorrentService(TorrentRepository(db)),
                    IndexerService(IndexerRepository(db)), NotificationService(NotificationRepository(db)),
                )
                show = service.get_show_by_id(show_id)
                for season in sorted(show.seasons, key=lambda item: item.number):
                    if season.number <= 0 or (season_number is not None and season.number != season_number):
                        continue
                    report["current_season"] = season.number
                    atomic_json(path, report)
                    try:
                        missing = missing_episodes(service, show, season, today)
                        if episode_number is not None:
                            missing &= {episode_number}
                        if not missing:
                            continue
                        choices = find_releases(service, show, season, missing, allow_pack=episode_number is None)
                        remaining = missing & missing_episodes(service, show, season, today)
                        covered = set().union(*(choice.episodes for choice in choices))
                        report["not_found"].extend(
                            {"season": season.number, "episode": number}
                            for number in sorted(remaining - covered)
                        )
                        for choice in choices:
                            if not choice.episodes <= missing_episodes(service, show, season, today):
                                continue
                            try:
                                if submit(service, season, choice):
                                    report["queued_downloads"] += 1
                                    report["queued_episodes"] += len(choice.episodes)
                            except HTTPException as error:
                                report["errors"].append({
                                    "season": season.number,
                                    "episodes": sorted(choice.episodes),
                                    "message": str(error.detail),
                                })
                            atomic_json(path, report)
                    except HTTPException as error:
                        db.rollback()
                        report["errors"].append({"season": season.number, "message": str(error.detail)})
                    except Exception as error:
                        db.rollback()
                        report["errors"].append({"season": season.number, "message": "Missing episode search failed. Check the server logs."})
                        log.error("Backfill failed for show %s season %s (%s)", show_id, season.number, type(error).__name__)
                report["status"] = "completed"
        except Exception as error:
            report["status"] = "failed"
            report["errors"].append({"season": None, "message": "Missing episode search failed. Check the server logs."})
            log.error("Backfill failed for show %s (%s)", show_id, type(error).__name__)
        finally:
            report["current_season"] = None
            atomic_json(path, report)
