"""Exercise PostgreSQL claims and mixed-protocol selection with a fake downloader."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from media_manager.config import MediaManagerConfig
from media_manager.database import init_engine
from media_manager.indexer.config import ReleasePolicyConfig
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.torrent.repository import TorrentRepository
from media_manager.torrent.schemas import Torrent, TorrentStatus
from media_manager.torrent.service import TorrentService
from media_manager.tv import backfill
from media_manager.tv.models import Episode, EpisodeDownload, Season, Show
from media_manager.tv.repository import TvRepository
from media_manager.tv.service import TvService
import media_manager.release_policy as policy_module

engine = init_engine(MediaManagerConfig().database)
today = datetime.now(ZoneInfo("Europe/Berlin")).date()
show_id, season_id = uuid.uuid4(), uuid.uuid4()
policy_module.MediaManagerConfig = lambda: SimpleNamespace(
    indexers=SimpleNamespace(release_policy=ReleasePolicyConfig(enabled=True))
)


def release(number, language="German", usenet=True):
    return IndexerQueryResult(
        title=f"Own.Backfill.S01E{number:02d}.{language}.1080p.WEB",
        download_url="http://localhost/fixture", seeders=6, flags=[], size=1,
        usenet=usenet, age=1, indexer="Fixture",
    )


class Downloader:
    submitted = []
    uncertain = False

    def supports_download(self, result):
        return True

    def download(self, result):
        self.submitted.append(result)
        if self.uncertain:
            raise TimeoutError("Fixture")
        return Torrent(
            title=result.title, status=TorrentStatus.downloading, quality=result.quality,
            hash=str(uuid.uuid4()), imported=False, usenet=result.usenet,
        )


class Indexer:
    indexers = [object()]

    def search_season(self, show, season_number):
        return [release(1, usenet=False), release(2, "English"), release(3)]

    def search(self, query, is_tv):
        return [release(int(query[-2:]))]


downloader = Downloader()
with Session(engine) as db:
    db.add(Show(
        id=show_id, external_id=9920231, metadata_provider="tmdb",
        name="Own Backfill", overview="", year=2026,
    ))
    db.flush()
    db.add(Season(id=season_id, show_id=show_id, number=1, external_id=9920231, name="S1", overview=""))
    db.flush()
    for number, days in [(1, -60), (2, -10), (3, 7), (4, -60)]:
        db.add(Episode(
            id=uuid.uuid4(), season_id=season_id, number=number, external_id=9920231 + number,
            title=f"Episode {number}", air_date=today + timedelta(days=days),
        ))
    db.commit()

    tv = TvService(TvRepository(db), TorrentService(TorrentRepository(db), downloader), Indexer(), None)
    show = tv.get_show_by_id(show_id)
    season = show.seasons[0]
    existing = tv.get_root_season_directory(show, 1) / "Own.Backfill.S01E04.mkv"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"Existing fixture")
    missing = backfill.missing_episodes(tv, show, season, today)
    assert missing == {1, 2}
    choices = backfill.find_releases(tv, show, season, missing)
    assert [(item.episodes, item.release.usenet) for item in choices] == [({1}, True), ({2}, True)]
    assert all("German" in item.release.title for item in choices)
    # Submit a torrent and an NZB for different episodes under the same season.
    choices[0].release = release(1, usenet=False)
    assert backfill.submit(tv, season, choices[0])
    assert not backfill.submit(tv, season, choices[0])
    downloader.uncertain = True
    try:
        backfill.submit(tv, season, choices[1])
    except HTTPException as error:
        assert error.status_code == 502
    else:
        raise AssertionError("Uncertain submission should be reported")
    assert db.get(EpisodeDownload, next(episode.id for episode in season.episodes if episode.number == 2)).status == "uncertain"
    assert backfill.missing_episodes(tv, show, season, today) == set()
    assert not backfill.submit(tv, season, choices[1])
    assert len(downloader.submitted) == 2
    assert existing.read_bytes() == b"Existing fixture"

    # A second job cannot start while a worker holds the series lease.
    from fastapi import BackgroundTasks
    tasks = BackgroundTasks()
    backfill.start(show_id, 1, tasks, 2)
    assert backfill.status(show_id)["episode_number"] == 2
    try:
        backfill.start(show_id, None, BackgroundTasks())
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("Concurrent search should be blocked")
    tasks.tasks[0].args[3].close()
    assert backfill.status(show_id)["status"] == "interrupted"

print("Backfill: existing/future skipped, selection, durable claims and concurrent jobs passed")
