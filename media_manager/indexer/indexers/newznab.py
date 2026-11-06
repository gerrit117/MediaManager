"""Direct Newznab client; see https://newznab.readthedocs.io/en/latest/misc/api.html."""

import hashlib
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import RLock
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

import requests
from pydantic import BaseModel

from media_manager.indexer.categories import (
    Category,
    selected_categories,
    torznab_categories,
)
from media_manager.indexer.indexers.generic import GenericIndexer
from media_manager.indexer.newznab_settings import (
    NewznabError,
    NewznabSettings,
    read_settings,
)
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.movies.schemas import Movie
from media_manager.tv.schemas import Show

log = logging.getLogger(__name__)
NAMESPACE = {"newznab": "http://www.newznab.com/DTD/2010/feeds/attributes/"}
CACHE: dict[str, tuple[float, "Capabilities"]] = {}
CACHE_LOCK = RLock()


class Capabilities(BaseModel):
    categories: list[Category]
    searches: dict[str, set[str]]
    limit: int


class Newznab(GenericIndexer):
    def __init__(self, settings: NewznabSettings | None = None) -> None:
        super().__init__(name="Treasure Maps")
        self.settings = settings or read_settings()

    def request(self, parameters: dict) -> ET.Element:
        """Hide URL-bearing requests exceptions and remote error descriptions."""
        try:
            response = requests.get(
                self.settings.url,
                params={
                    **parameters,
                    "apikey": self.settings.api_key.get_secret_value(),
                    "o": "xml",
                },
                timeout=(5, 25),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise NewznabError(NewznabError.CONNECTION) from None
        if response.status_code in {401, 403}:
            raise NewznabError(NewznabError.AUTH)
        if response.status_code == 429:
            raise NewznabError(NewznabError.LIMIT)
        if 300 <= response.status_code < 400:
            raise NewznabError(NewznabError.REDIRECT)
        if response.status_code >= 400:
            raise NewznabError(NewznabError.CONNECTION)
        try:
            root = ET.fromstring(response.content)  # noqa: S314
        except ET.ParseError:
            raise NewznabError(NewznabError.INVALID_XML) from None
        if root.tag == "error":
            code = root.get("code", "")
            if code in {"100", "101", "102"}:
                raise NewznabError(NewznabError.AUTH)
            if code in {"202", "203"}:
                raise NewznabError(NewznabError.UNSUPPORTED)
            raise NewznabError(NewznabError.REJECTED)
        return root

    def capabilities(self, refresh: bool = False) -> Capabilities:
        identifier = hashlib.sha256(
            (self.settings.url + self.settings.api_key.get_secret_value()).encode()
        ).hexdigest()
        with CACHE_LOCK:
            cached = CACHE.get(identifier)
            if not refresh and cached and time.monotonic() - cached[0] < 300:
                return cached[1]
        root = self.request({"t": "caps"})
        if root.tag != "caps":
            raise NewznabError(NewznabError.CAPS)
        searches = {}
        for node in root.findall("searching/*"):
            if node.get("available", "no").lower() == "yes":
                searches[node.tag] = {
                    value.strip().lower()
                    for value in node.get("supportedParams", "").split(",")
                    if value.strip()
                }
        limits = root.find("limits")
        try:
            limit = (
                min(100, max(1, int(limits.get("max", "100"))))
                if limits is not None
                else 100
            )
            categories = torznab_categories(ET.tostring(root))
        except (ValueError, KeyError):
            raise NewznabError(NewznabError.INVALID_CAPS) from None
        caps = Capabilities(categories=categories, searches=searches, limit=limit)
        with CACHE_LOCK:
            if len(CACHE) >= 16:
                CACHE.clear()
            CACHE[identifier] = (time.monotonic(), caps)
        return caps

    def test_connection(self) -> Capabilities:
        if not self.settings.api_key.get_secret_value():
            raise NewznabError(NewznabError.KEY_REQUIRED)
        caps = self.capabilities(refresh=True)
        if "search" not in caps.searches:
            raise NewznabError(NewznabError.SEARCH_REQUIRED)
        # CAPS can be public; an authenticated SEARCH also verifies the API key.
        root = self.request(
            {"t": "search", "q": "mediamanager-connection-check", "limit": 1}
        )
        if root.tag != "rss" or root.find("channel") is None:
            raise NewznabError(NewznabError.INVALID_SEARCH)
        return caps

    def parse_results(self, root: ET.Element) -> list[IndexerQueryResult]:
        results = []
        for item in root.findall("channel/item"):
            try:
                enclosure = item.find("enclosure")
                attrs = {
                    n.get("name"): n.get("value")
                    for n in item.findall("newznab:attr", NAMESPACE)
                }
                if enclosure is None:
                    continue
                download_url = urljoin(self.settings.url, enclosure.get("url", ""))
                if not enclosure.get("url") or urlsplit(download_url).scheme not in {
                    "https",
                    "http",
                }:
                    continue
                # Authenticated enclosure URLs are passed through unchanged to SABnzbd.
                size = int(
                    attrs.get("size")
                    or enclosure.get("length")
                    or item.findtext("size")
                    or "0"
                )
                if size <= 0:
                    continue
                age = 0
                date = attrs.get("usenetdate") or item.findtext("pubDate")
                if date:
                    try:
                        posted = parsedate_to_datetime(date)
                        if posted.tzinfo is None:
                            posted = posted.replace(tzinfo=UTC)
                        age = max(0, int((datetime.now(UTC) - posted).total_seconds()))
                    except (ValueError, TypeError, OverflowError):
                        pass
                results.append(
                    IndexerQueryResult(
                        title=item.findtext("title") or "unknown",
                        download_url=download_url,
                        seeders=0,
                        flags=[],
                        size=size,
                        usenet=True,
                        age=age,
                        indexer=self.name,
                    )
                )
            except (ValueError, TypeError):
                log.warning("Skipped a malformed Newznab result.")
        return results

    def _search(
        self,
        query: str,
        is_tv: bool,
        media: Movie | Show | None = None,
        season: int | None = None,
    ) -> list[IndexerQueryResult]:
        caps = self.capabilities()
        function = "tv-search" if is_tv else "movie-search"
        if function not in caps.searches:
            function = "search"
        if function not in caps.searches:
            raise NewznabError(NewznabError.NO_SEARCH)
        supported = caps.searches[function]
        params: dict = {
            "t": {"tv-search": "tvsearch", "movie-search": "movie"}.get(
                function, "search"
            )
        }
        if "q" in supported or function == "search":
            params["q"] = query
        if media is not None:
            provider = getattr(media, "metadata_provider", None)
            identifier = getattr(media, "external_id", None)
            if (
                provider in {"tmdb", "tvdb"}
                and f"{provider}id" in supported
                and identifier
            ):
                params[f"{provider}id"] = identifier
            imdb = getattr(media, "imdb_id", None)
            if imdb and "imdbid" in supported:
                params["imdbid"] = str(imdb).removeprefix("tt")
        if any(key in params for key in {"tmdbid", "tvdbid", "imdbid"}):
            params.pop("q", None)
        if season is not None and "season" in supported:
            params["season"] = season
        if not any(key in params for key in {"q", "tmdbid", "tvdbid", "imdbid"}):
            raise NewznabError(NewznabError.UNSEARCHABLE)
        categories = selected_categories("newznab", "treasure-maps", is_tv)
        params["cat"] = ",".join(map(str, categories or ([5000] if is_tv else [2000])))
        params.update({"extended": 1, "limit": caps.limit})
        results = []
        seen = set()
        offset = 0
        # Bound API usage, obey page sizes, and stop on repeated/empty pages.
        for _ in range(5):
            root = self.request({**params, "offset": offset})
            if root.tag != "rss" or root.find("channel") is None:
                raise NewznabError(NewznabError.INVALID_SEARCH)
            batch = self.parse_results(root)
            fresh = []
            for result in batch:
                if result.download_url not in seen:
                    fresh.append(result)
                    seen.add(result.download_url)
            results.extend(fresh)
            count = len(root.findall("channel/item"))
            info = root.find("channel/newznab:response", NAMESPACE)
            offset += count
            if not fresh or count < caps.limit or info is None:
                break
            try:
                if offset >= int(info.get("total", "0")):
                    break
            except ValueError:
                break
        return results

    def search(self, query: str, is_tv: bool) -> list[IndexerQueryResult]:
        return self._search(query, is_tv)

    def search_movie(self, query: str, movie: Movie) -> list[IndexerQueryResult]:
        return self._search(query, False, movie)

    def search_season(
        self, query: str, show: Show, season_number: int
    ) -> list[IndexerQueryResult]:
        return self._search(query, True, show, season_number)
