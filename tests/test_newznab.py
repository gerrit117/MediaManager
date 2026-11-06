"""Direct Newznab requests, authentication, persistence and parser regressions."""
# ruff: noqa: ANN001, ANN201, ANN202, S101

import traceback
from types import SimpleNamespace
from unittest.mock import Mock
from xml.etree import ElementTree as ET

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from media_manager.auth.users import current_superuser, get_async_session
from media_manager.indexer import categories, newznab_settings, router
from media_manager.indexer.categories import CategorySelection
from media_manager.indexer.indexers import newznab
from media_manager.indexer.newznab_settings import NewznabError, NewznabSettings

CAPS = b"""<caps><limits max="2" default="1"/><searching>
<search available="yes" supportedParams="q"/>
<tv-search available="yes" supportedParams="q,tvdbid,tmdbid,imdbid,season"/>
<movie-search available="yes" supportedParams="q,imdbid,tmdbid"/>
</searching><categories><category id="2100" name="Movies - DE"><subcat id="2140" name="HD"/></category>
<category id="5100" name="TV - DE"/></categories></caps>"""


def rss(ids, total=1):
    items = "".join(
        f"""<item><title>Example.German.1080p.{i}</title><pubDate>Mon, 02 Nov 2026 12:00:00 +0000</pubDate>
<enclosure url="https://indexer.test/api?t=get&amp;id={i}&amp;apikey=download-secret" length="1234" type="application/x-nzb"/>
<newznab:attr name="size" value="2345"/></item>"""
        for i in ids
    )
    return f"""<rss xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/"><channel>
<newznab:response offset="0" total="{total}"/>{items}</channel></rss>""".encode()


@pytest.fixture(autouse=True)
def storage(monkeypatch, tmp_path):
    monkeypatch.setattr(
        categories, "selection_path", lambda: tmp_path / "categories.json"
    )
    monkeypatch.setattr(
        newznab_settings, "settings_path", lambda: tmp_path / "newznab.json"
    )
    newznab.CACHE.clear()
    return tmp_path


@pytest.fixture
def client(monkeypatch):
    response = Mock(status_code=200, content=CAPS)
    get = Mock(return_value=response)
    monkeypatch.setattr(newznab.requests, "get", get)
    return newznab.Newznab(
        NewznabSettings(
            enabled=True,
            url="https://indexer.test/api",
            api_key=SecretStr("test-secret"),
        )
    ), get


def response(content, status=200):
    return SimpleNamespace(status_code=status, content=content)


def test_secret_storage_and_blank_key_retention(storage):
    settings = NewznabSettings(enabled=True, api_key=SecretStr("test-secret"))
    newznab_settings.save_settings(settings)
    assert (storage / "newznab.json").stat().st_mode & 0o777 == 0o600
    assert newznab_settings.read_settings().api_key.get_secret_value() == "test-secret"
    view = newznab_settings.public_settings(settings).model_dump_json()
    assert "test-secret" not in view
    assert "api_key" not in newznab_settings.public_settings(settings).model_dump()
    assert (
        newznab_settings.prepare_settings(
            NewznabSettings(enabled=True)
        ).api_key.get_secret_value()
        == "test-secret"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:password@indexer.test/api",
        "https://indexer.test/api?apikey=test-secret",
        "https://indexer.test/api#test-secret",
    ],
)
def test_credentials_in_url_rejected(url):
    with pytest.raises(NewznabError, match="without credentials"):
        newznab_settings.prepare_settings(NewznabSettings(url=url))


def test_capabilities_and_cache(client):
    indexer, get = client
    caps = indexer.capabilities()
    assert caps.limit == 2
    assert {c.id for c in caps.categories} == {2100, 2140, 5100}
    assert "season" in caps.searches["tv-search"]
    indexer.capabilities()
    assert get.call_count == 1
    assert get.call_args.kwargs["allow_redirects"] is False


def test_connection_checks_auth_beyond_public_caps(client):
    indexer, get = client
    get.side_effect = [
        response(CAPS),
        response(b'<error code="100" description="test-secret"/>'),
    ]
    with pytest.raises(NewznabError, match="authentication") as error:
        indexer.test_connection()
    assert "test-secret" not in str(error.value)
    assert get.call_args.kwargs["params"]["t"] == "search"
    assert get.call_args.kwargs["params"]["limit"] == 1


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"bad xml", 200),
        (b'<error code="500" description="test-secret"/>', 200),
        (b"", 429),
        (b"", 302),
        (b"", 403),
        (b"", 500),
    ],
)
def test_safe_error_responses(client, content, status):
    indexer, get = client
    get.return_value = response(content, status)
    with pytest.raises(NewznabError) as error:
        indexer.request({"t": "search"})
    assert "test-secret" not in str(error.value)


def test_network_exception_never_exposes_url_or_key(client):
    indexer, get = client
    get.side_effect = requests.ConnectionError(
        "https://indexer.test/api?apikey=test-secret"
    )
    try:
        indexer.request({"t": "caps"})
    except NewznabError:
        rendered = traceback.format_exc()
        assert "test-secret" not in rendered
        assert "indexer.test" not in rendered


def test_parser_preserves_download_url_and_size(client):
    indexer, _ = client
    result = indexer.parse_results(ET.fromstring(rss(["a"])))[0]  # noqa: S314
    assert result.download_url.endswith("id=a&apikey=download-secret")
    assert result.size == 2345
    assert result.usenet
    assert result.age >= 0
    assert result.indexer == "Treasure Maps"
    assert "download-secret" not in result.model_dump_json()


@pytest.mark.parametrize("tv", [True, False])
def test_category_and_id_search(client, tv):
    indexer, get = client
    categories.save_selection(
        "newznab",
        "treasure-maps",
        CategorySelection(movie_categories=[2100], tv_categories=[5100]),
    )
    get.side_effect = [response(CAPS), response(rss(["a"]))]
    media = SimpleNamespace(metadata_provider="tmdb", external_id=42, imdb_id="tt123")
    if tv:
        indexer.search_season("Example S02", media, 2)
    else:
        indexer.search_movie("Example 2026", media)
    params = get.call_args.kwargs["params"]
    assert params["cat"] == ("5100" if tv else "2100")
    assert params["tmdbid"] == 42
    assert params["imdbid"] == "123"
    assert params["t"] == ("tvsearch" if tv else "movie")
    assert ("season" in params) == tv


def test_fallback_and_pagination(client):
    indexer, get = client
    caps = CAPS.replace(
        b'<movie-search available="yes"', b'<movie-search available="no"'
    )
    get.side_effect = [
        response(caps),
        response(rss(["a", "b"], 3)),
        response(rss(["c"], 3)),
    ]
    result = indexer.search("Example", False)
    assert len(result) == 3
    assert get.call_args.kwargs["params"]["offset"] == 2
    assert get.call_args.kwargs["params"]["t"] == "search"
    assert "season" not in get.call_args.kwargs["params"]


def test_repeated_page_stops(client):
    indexer, get = client
    get.side_effect = [
        response(CAPS),
        response(rss(["a", "b"], 20)),
        response(rss(["a", "b"], 20)),
    ]
    assert len(indexer.search("Example", False)) == 2
    assert get.call_count == 3


def test_settings_api_access_and_secrets(monkeypatch):
    app = FastAPI()
    app.include_router(router.router)

    async def unused_session():
        yield None

    app.dependency_overrides[get_async_session] = unused_session
    web = TestClient(app)
    assert web.get("/newznab").status_code == 401
    assert web.put("/newznab", json={}).status_code == 401
    assert web.post("/newznab/test", json={}).status_code == 401
    app.dependency_overrides[current_superuser] = lambda: object()
    monkeypatch.setattr(newznab.Newznab, "test_connection", Mock())
    saved = web.put(
        "/newznab",
        json={
            "enabled": True,
            "url": "https://indexer.test/api",
            "api_key": "test-secret",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["has_api_key"]
    assert "test-secret" not in saved.text + web.get("/newznab").text
    assert (
        web.put(
            "/newznab",
            json={"enabled": True, "url": "https://indexer.test/api", "api_key": ""},
        ).status_code
        == 200
    )
    assert newznab_settings.read_settings().api_key.get_secret_value() == "test-secret"
    newznab.Newznab.test_connection.side_effect = NewznabError(NewznabError.AUTH)
    assert (
        web.put(
            "/newznab",
            json={"enabled": True, "url": "https://indexer.test/api", "api_key": "bad"},
        ).status_code
        == 400
    )
    assert newznab_settings.read_settings().api_key.get_secret_value() == "test-secret"
    assert (
        web.put(
            "/newznab", json={"enabled": False, "url": "https://indexer.test/api"}
        ).status_code
        == 200
    )


def test_service_uses_direct_connection(monkeypatch):
    from media_manager.indexer import service

    newznab_settings.save_settings(
        NewznabSettings(enabled=True, api_key=SecretStr("test-secret"))
    )
    monkeypatch.setattr(
        service,
        "MediaManagerConfig",
        lambda: SimpleNamespace(
            indexers=SimpleNamespace(
                prowlarr=SimpleNamespace(enabled=False),
                jackett=SimpleNamespace(enabled=False),
            )
        ),
    )
    repository = Mock()
    indexers = service.IndexerService(repository)
    assert len(indexers.indexers) == 1
    assert isinstance(indexers.indexers[0], newznab.Newznab)
    result = indexers.indexers[0].parse_results(ET.fromstring(rss(["a"])))[0]  # noqa: S314
    monkeypatch.setattr(newznab.Newznab, "search", lambda *_args, **_kwargs: [result])
    assert indexers.search("Example", False) == [result]
    repository.save_result.assert_called_once_with(result=result)
