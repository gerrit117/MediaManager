"""Private, persistent settings for the initial Treasure Maps connection."""

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, SecretStr

from media_manager.indexer.categories import LOCK, selection_path


class NewznabError(Exception):
    """Safe message for the UI and logs; never includes credentials or URLs."""

    CONFIG = "Could not read the saved Newznab configuration."
    URL = "Enter an HTTP(S) API URL without credentials or query parameters."
    KEY_REQUIRED = "Enter an API key before enabling the indexer."
    AUTH = "Indexer authentication failed. Check your API key and account."
    LIMIT = "Indexer API limit reached. Try again later."
    REDIRECT = "The API URL redirects. Enter the final API URL in Settings."
    CONNECTION = "Could not reach the indexer API. Check its URL and connection."
    INVALID_XML = "The indexer did not return valid Newznab XML."
    UNSUPPORTED = "The indexer does not support this search function."
    REJECTED = "The indexer rejected the request. Check the connection settings."
    CAPS = "The API URL did not return Newznab capabilities."
    INVALID_CAPS = "The indexer returned invalid capability data."
    SEARCH_REQUIRED = "This connection requires the standard Newznab search function."
    INVALID_SEARCH = "The indexer did not return a valid Newznab search response."
    UNSEARCHABLE = (
        "The indexer cannot search this title with its advertised parameters."
    )
    NO_SEARCH = "The indexer does not advertise a supported search function."


class NewznabSettings(BaseModel):
    enabled: bool = False
    url: str = "https://treasure-maps.com/api"
    api_key: SecretStr = SecretStr("")


class NewznabSettingsView(BaseModel):
    name: str = "Treasure Maps"
    enabled: bool
    url: str
    has_api_key: bool


def settings_path() -> Path:
    return selection_path().parent / "newznab.json"


def read_settings() -> NewznabSettings:
    with LOCK:
        path = settings_path()
        if not path.exists():
            return NewznabSettings()
        try:
            return NewznabSettings.model_validate_json(path.read_text())
        except ValueError:
            raise NewznabError(NewznabError.CONFIG) from None


def public_settings(settings: NewznabSettings) -> NewznabSettingsView:
    return NewznabSettingsView(
        enabled=settings.enabled,
        url=settings.url,
        has_api_key=bool(settings.api_key.get_secret_value()),
    )


def prepare_settings(settings: NewznabSettings) -> NewznabSettings:
    """A blank key keeps the existing secret; reject credentials in URLs."""
    settings = settings.model_copy(deep=True)
    settings.url = settings.url.strip().rstrip("/")
    try:
        parsed = urlsplit(settings.url)
        valid = (
            parsed.scheme in {"https", "http"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise NewznabError(NewznabError.URL)
    if not settings.api_key.get_secret_value():
        settings.api_key = read_settings().api_key
    if settings.enabled and not settings.api_key.get_secret_value():
        raise NewznabError(NewznabError.KEY_REQUIRED)
    return settings


def save_settings(settings: NewznabSettings) -> None:
    with LOCK:
        path = settings_path()
        data = settings.model_dump(mode="json", exclude={"api_key"})
        data["api_key"] = settings.api_key.get_secret_value()
        descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".newznab-")
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump(data, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
