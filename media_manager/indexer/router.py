"""Administrator settings for categories advertised by configured indexers."""

from xml.etree.ElementTree import ParseError

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from media_manager.auth.users import current_superuser
from media_manager.config import MediaManagerConfig
from media_manager.indexer.categories import (
    Category,
    CategorySelection,
    prowlarr_categories,
    read_selections,
    save_selection,
    torznab_categories,
)
from media_manager.indexer.indexers.newznab import Newznab
from media_manager.indexer.indexers.prowlarr import Prowlarr
from media_manager.indexer.newznab_settings import (
    NewznabError,
    NewznabSettings,
    NewznabSettingsView,
    prepare_settings,
    public_settings,
    read_settings,
    save_settings,
)

router = APIRouter(dependencies=[Depends(current_superuser)])


class IndexerCategories(BaseModel):
    provider: str
    indexer_id: str
    name: str
    categories: list[Category] = Field(default_factory=list)
    selection: CategorySelection = Field(default_factory=CategorySelection)
    error: str | None = None


def discover_categories() -> list[IndexerCategories]:
    config = MediaManagerConfig().indexers
    saved = read_selections()
    result = []
    direct = read_settings()
    if direct.api_key.get_secret_value() or direct.enabled:
        item = IndexerCategories(
            provider="newznab",
            indexer_id="treasure-maps",
            name="Treasure Maps",
            selection=CategorySelection.model_validate(
                saved.get("newznab:treasure-maps", {})
            ),
        )
        try:
            item.categories = Newznab(direct).capabilities().categories
        except NewznabError as error:
            item.error = str(error)
        result.append(item)
    if config.prowlarr.enabled:
        try:
            response = Prowlarr()._call_prowlarr_api("/indexer")
            response.raise_for_status()
            for indexer in response.json():
                identifier = str(indexer["id"])
                result.append(
                    IndexerCategories(
                        provider="prowlarr",
                        indexer_id=identifier,
                        name=indexer["name"],
                        categories=prowlarr_categories(
                            indexer.get("capabilities", {}).get("categories", [])
                        ),
                        selection=CategorySelection.model_validate(
                            saved.get(f"prowlarr:{identifier}", {})
                        ),
                    )
                )
        except (requests.RequestException, ValueError, KeyError):
            result.append(
                IndexerCategories(
                    provider="prowlarr",
                    indexer_id="",
                    name="Prowlarr",
                    error="Could not load indexer categories. Check the connection settings.",
                )
            )
    if config.jackett.enabled:
        for identifier in config.jackett.indexers:
            item = IndexerCategories(
                provider="jackett",
                indexer_id=identifier,
                name=identifier,
                selection=CategorySelection.model_validate(
                    saved.get(f"jackett:{identifier}", {})
                ),
            )
            try:
                response = requests.get(
                    f"{config.jackett.url}/api/v2.0/indexers/{identifier}/results/torznab/api",
                    params={"apikey": config.jackett.api_key, "t": "caps"},
                    timeout=config.jackett.timeout_seconds,
                )
                response.raise_for_status()
                item.categories = torznab_categories(response.content)
            except (requests.RequestException, ValueError, KeyError, ParseError):
                item.error = "Could not load categories. Check the indexer connection."
            result.append(item)
    return result


@router.get("/categories")
def get_categories() -> list[IndexerCategories]:
    return discover_categories()


@router.put("/categories/{provider}/{indexer_id}")
def update_categories(
    provider: str, indexer_id: str, selection: CategorySelection
) -> CategorySelection:
    indexer = next(
        (
            item
            for item in discover_categories()
            if item.provider == provider and item.indexer_id == indexer_id
        ),
        None,
    )
    if indexer is None:
        raise HTTPException(404, "Indexer is not configured.")
    if indexer.error:
        raise HTTPException(503, indexer.error)
    known = {category.id for category in indexer.categories}
    selected = set(selection.movie_categories + selection.tv_categories)
    if not selected <= known:
        raise HTTPException(422, "Select categories advertised by this indexer.")
    selection.movie_categories = list(dict.fromkeys(selection.movie_categories))
    selection.tv_categories = list(dict.fromkeys(selection.tv_categories))
    save_selection(provider, indexer_id, selection)
    return selection


@router.get("/newznab")
def get_newznab_settings() -> NewznabSettingsView:
    return public_settings(read_settings())


@router.put("/newznab")
def update_newznab_settings(settings: NewznabSettings) -> NewznabSettingsView:
    try:
        settings = prepare_settings(settings)
        if settings.enabled:
            Newznab(settings).test_connection()
        save_settings(settings)
    except NewznabError as error:
        raise HTTPException(400, str(error)) from None
    return public_settings(settings)


@router.post("/newznab/test")
def test_newznab_connection(settings: NewznabSettings) -> dict:
    try:
        settings = prepare_settings(settings)
        caps = Newznab(settings).test_connection()
    except NewznabError as error:
        raise HTTPException(400, str(error)) from None
    return {
        "message": "Connection and API key verified. No download was started.",
        "categories": len(caps.categories),
        "search_functions": sorted(caps.searches),
    }
