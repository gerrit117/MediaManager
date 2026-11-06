"""Category discovery, persistence and search parameter regression tests."""
# ruff: noqa: ANN001, ANN201, ANN202, S101

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from media_manager.auth.users import current_superuser, get_async_session
from media_manager.indexer import categories
from media_manager.indexer import router as settings
from media_manager.indexer.categories import CategorySelection
from media_manager.indexer.indexers.jackett import Jackett
from media_manager.indexer.indexers.prowlarr import IndexerInfo, Prowlarr


@pytest.fixture(autouse=True)
def selection_file(monkeypatch, tmp_path):
    path = tmp_path / "categories.json"
    monkeypatch.setattr(categories, "selection_path", lambda: path)
    return path


def test_nested_and_custom_categories():
    result = categories.prowlarr_categories(
        [
            {
                "id": 2000,
                "name": "Movies",
                "subCategories": [{"id": 2100, "name": "German"}],
            },
            {"id": 5100, "name": "TV German"},
            {"id": 100123, "name": "Custom"},
        ]
    )
    assert [category.id for category in result] == [2000, 2100, 5100, 100123]
    xml = b'<caps><categories><category id="2000" name="Movies"><subcat id="2100" name="German"/></category><category id="5100" name="TV German"/></categories></caps>'
    assert [category.id for category in categories.torznab_categories(xml)] == [
        2000,
        5100,
        2100,
    ]


def test_missing_selection_keeps_defaults():
    assert categories.selected_categories("prowlarr", "1", True) == []


def test_persistence_and_concurrent_indexers(selection_file):
    def save(number):
        categories.save_selection(
            "prowlarr",
            str(number),
            CategorySelection(movie_categories=[2100], tv_categories=[5100]),
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(save, range(10)))
    assert len(categories.read_selections()) == 10
    assert categories.selected_categories("prowlarr", "2", True) == [5100]
    assert categories.selected_categories("prowlarr", "2", False) == [2100]
    assert selection_file.stat().st_mode & 0o777 == 0o600


@pytest.fixture
def prowlarr(monkeypatch):
    client = Prowlarr()
    info = IndexerInfo(1, "Test", True, True, True, True, True, True, True, True, True)
    monkeypatch.setattr(client, "_get_tv_indexers", lambda: [info])
    monkeypatch.setattr(client, "_get_movie_indexers", lambda: [info])
    client._call_prowlarr_api = Mock(return_value=SimpleNamespace(content=b"<rss/>"))
    client.process_search_result = Mock(return_value=[])
    return client


@pytest.mark.parametrize(
    ("method", "is_tv"),
    [
        ("search", True),
        ("search", False),
        ("search_season", True),
        ("search_movie", False),
    ],
)
def test_prowlarr_search_uses_selection(prowlarr, method, is_tv):
    categories.save_selection(
        "prowlarr",
        "1",
        CategorySelection(movie_categories=[2100, 100123], tv_categories=[5100]),
    )
    media = SimpleNamespace(metadata_provider="tmdb", external_id=12, imdb_id="tt12")
    if method == "search":
        prowlarr.search("Example", is_tv)
    elif method == "search_movie":
        prowlarr.search_movie("Example", media)
    else:
        prowlarr.search_season("Example", media, 2)
    params = prowlarr._call_prowlarr_api.call_args.kwargs["parameters"]
    assert params["cat"] == ("5100" if is_tv else "2100,100123")


def test_prowlarr_legacy_default(prowlarr):
    prowlarr.search_season(
        "Example",
        SimpleNamespace(metadata_provider="tmdb", external_id=12, imdb_id=None),
        2,
    )
    assert prowlarr._call_prowlarr_api.call_args.kwargs["parameters"]["cat"] == "5000"


@pytest.mark.parametrize("is_tv", [True, False])
def test_jackett_search_parameters(monkeypatch, is_tv):
    client = Jackett()
    monkeypatch.setattr(
        client,
        "_Jackett__get_optimal_query_parameters",
        lambda **_kwargs: {"q": "Example"},
    )
    client.process_search_result = Mock(return_value=[])
    categories.save_selection(
        "jackett",
        "test",
        CategorySelection(movie_categories=[2100], tv_categories=[5100]),
    )
    session = Mock()
    session.get.return_value = SimpleNamespace(
        status_code=200, content=b"<rss/>", url="http://localhost/test"
    )
    client.get_torrents_by_indexer(
        "test", {"t": "tvsearch" if is_tv else "movie"}, session
    )
    assert session.get.call_args.kwargs["params"]["cat"] == (
        "5100" if is_tv else "2100"
    )


@pytest.fixture
def web(monkeypatch):
    app = FastAPI()
    app.include_router(settings.router)

    async def unused_session():
        yield None

    app.dependency_overrides[get_async_session] = unused_session
    monkeypatch.setattr(
        settings,
        "discover_categories",
        lambda: [
            settings.IndexerCategories(
                provider="prowlarr",
                indexer_id="1",
                name="Test",
                categories=[categories.Category(id=2100, name="German")],
            )
        ],
    )
    return app, TestClient(app)


def test_administrator_required(web):
    _app, client = web
    assert client.get("/categories").status_code == 401


def test_unknown_category_and_persistence(web):
    app, client = web
    app.dependency_overrides[current_superuser] = lambda: object()
    assert (
        client.put(
            "/categories/prowlarr/1", json={"movie_categories": [9999]}
        ).status_code
        == 422
    )
    assert categories.read_selections() == {}
    assert client.put(
        "/categories/prowlarr/1", json={"movie_categories": [2100, 2100]}
    ).json()["movie_categories"] == [2100]
    assert categories.selected_categories("prowlarr", "1", False) == [2100]
    assert client.put("/categories/prowlarr/unknown", json={}).status_code == 404


def test_connection_error_preserves_selection(monkeypatch):
    categories.save_selection(
        "prowlarr", "1", CategorySelection(movie_categories=[2100])
    )
    config = SimpleNamespace(
        indexers=SimpleNamespace(
            prowlarr=SimpleNamespace(enabled=True),
            jackett=SimpleNamespace(enabled=False),
        )
    )
    monkeypatch.setattr(settings, "MediaManagerConfig", lambda: config)
    monkeypatch.setattr(
        Prowlarr,
        "_call_prowlarr_api",
        Mock(side_effect=requests.ConnectionError("private-url")),
    )
    result = settings.discover_categories()
    assert result[0].error
    assert "private-url" not in result[0].error
    assert categories.selected_categories("prowlarr", "1", False) == [2100]
