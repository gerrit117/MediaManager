from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from media_manager.indexer.config import ReleasePolicyConfig
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.tv import backfill
from media_manager.tv.schemas import Episode, Season


def release(title, *, usenet=True, seeders=10):
    return IndexerQueryResult(
        title=title, download_url="https://example.invalid/release", seeders=seeders,
        flags=[], size=1, usenet=usenet, age=1, indexer="Fixture",
    )


def test_backfill_prioritizes_language_and_keeps_partial_seasons_intact(monkeypatch):
    import media_manager.config
    import media_manager.release_policy

    config = lambda: SimpleNamespace(indexers=SimpleNamespace(release_policy=ReleasePolicyConfig(enabled=True)))
    monkeypatch.setattr(media_manager.config, "MediaManagerConfig", config)
    monkeypatch.setattr(media_manager.release_policy, "MediaManagerConfig", config)
    season = Season(number=1, external_id=1, name="Season", overview="", episodes=[
        Episode(number=i, external_id=i, title=str(i)) for i in (1, 2)
    ])
    english_pack = release("Fixture.S01.English.720p")
    german_pack = release("Fixture.S01.German.2160p")
    episode_one = release("Fixture.S01E01.German.720p", usenet=False)
    episode_two = release("Fixture.S01E02.English.1080p")
    remux = release("Fixture.S01E02.German.2160p.REMUX")
    dormant = release("Fixture.S01E02.German.1080p", usenet=False, seeders=0)
    season_search = Mock(side_effect=lambda *args, **kwargs: (
        [episode_one] if kwargs.get("search_query_override", "").endswith("E01") else
        [episode_two, remux, dormant] if kwargs.get("search_query_override") else
        [english_pack, episode_two]
    ))
    service = SimpleNamespace(
        get_all_available_torrents_for_a_season=season_search,
        indexer_service=SimpleNamespace(indexers=[object()]),
        torrent_service=SimpleNamespace(download_manager=SimpleNamespace(supports_download=lambda result: True)),
    )
    show = SimpleNamespace(name="Fixture", id="fixture")
    plan = backfill.find_releases(service, show, season, {1, 2})
    assert [(choice.release, choice.episodes) for choice in plan] == [(episode_one, {1}), (episode_two, {2})]

    assert backfill.select_releases(season, {1, 2}, [german_pack, episode_one, episode_two], allow_pack=True) == [
        backfill.ReleaseChoice(german_pack, {1, 2})
    ]
    assert backfill.select_releases(season, {1, 2}, [english_pack, episode_one], allow_pack=True) == [
        backfill.ReleaseChoice(english_pack, {2}), backfill.ReleaseChoice(episode_one, {1})
    ]
    assert backfill.select_releases(season, {2}, [german_pack, episode_one, episode_two], allow_pack=False) == [
        backfill.ReleaseChoice(episode_two, {2})
    ]
    assert backfill.find_releases(service, show, season, {2}, allow_pack=False) == [
        backfill.ReleaseChoice(episode_two, {2})
    ]


def test_missing_excludes_present_active_reserved_and_future(monkeypatch):
    today = date(2026, 11, 13)
    season = Season(number=1, external_id=1, name="Season", overview="", episodes=[
        Episode(number=i, external_id=i, title=str(i), air_date=air_date)
        for i, air_date in enumerate([today, today, today, today, today + timedelta(days=1), None], 1)
    ])
    db = SimpleNamespace(scalars=lambda _: [SimpleNamespace(episode_id=season.episodes[2].id)])
    service = SimpleNamespace(tv_repository=SimpleNamespace(db=db))
    monkeypatch.setattr(backfill, "season_presence", lambda *args: {1})
    monkeypatch.setattr(backfill, "claimed_episodes", lambda *args: {2})
    assert backfill.missing_episodes(service, object(), season, today) == {4}
