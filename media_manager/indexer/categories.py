"""Discover indexer categories and persist administrator selections."""

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

LOCK = RLock()


class Category(BaseModel):
    id: int
    name: str


class CategorySelection(BaseModel):
    movie_categories: list[int] = Field(default_factory=list)
    tv_categories: list[int] = Field(default_factory=list)


def selection_path() -> Path:
    from media_manager.config import config_path

    return Path(config_path).parent / "indexer-categories.json"


def read_selections() -> dict:
    path = selection_path()
    with LOCK:
        if not path.exists():
            return {}
        return json.loads(path.read_text())


def selected_categories(provider: str, indexer: str, is_tv: bool) -> list[int]:
    selection = read_selections().get(f"{provider}:{indexer}", {})
    return selection.get("tv_categories" if is_tv else "movie_categories", [])


def save_selection(provider: str, indexer: str, selection: CategorySelection) -> None:
    path = selection_path()
    with LOCK:
        selections = read_selections()
        selections[f"{provider}:{indexer}"] = selection.model_dump()
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".categories-")
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump(selections, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(path)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()


def prowlarr_categories(categories: list[dict]) -> list[Category]:
    result = {}

    def visit(nodes: list[dict]) -> None:
        for node in nodes:
            category = Category(id=node["id"], name=node["name"])
            result[category.id] = category
            visit(node.get("subCategories") or [])

    visit(categories)
    return list(result.values())


def torznab_categories(content: bytes) -> list[Category]:
    root = ET.fromstring(content)  # noqa: S314
    return [
        Category(id=int(node.attrib["id"]), name=node.attrib["name"])
        for node in root.findall(".//categories/category")
        + root.findall(".//categories/category/subcat")
    ]
