"""Admin-only metadata editing without changing library paths or internal identities."""
from copy import deepcopy
from time import monotonic
from typing import Literal
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from media_manager.auth.users import current_superuser
from media_manager.database import DbSessionDependency
from media_manager.metadataProvider.dependencies import get_metadata_provider

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(current_superuser)])
_cache = {}

class MetadataEdit(BaseModel):
    provider: Literal['tmdb', 'tvdb']
    external_id: int = Field(gt=0)
    previous_provider: Literal['tmdb', 'tvdb']
    previous_external_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1800, le=2200)
    overview: str = Field(default='', max_length=50000)
    refresh_metadata: bool = False
    confirm_identity_change: bool = False


def model_type(kind):
    from media_manager.movies.models import Movie
    from media_manager.tv.models import Show
    return Show if kind == 'tv' else Movie


def load_metadata(kind, provider, external_id, language=None):
    key = (kind, provider, external_id, language)
    item = _cache.get(key)
    if item and monotonic() - item[0] < 120:
        return deepcopy(item[1])
    api = get_metadata_provider(provider)
    try:
        fresh = api.get_show_metadata(show_id=external_id, language=language) if kind == 'tv' else api.get_movie_metadata(movie_id=external_id, language=language)
        if fresh is None or fresh.external_id != external_id or fresh.metadata_provider != provider:
            raise ValueError('Metadata identity mismatch')
    except Exception:
        log.warning('Metadata provider could not load %s %s ID %s', kind, provider, external_id)
        raise HTTPException(502, 'Metadata could not be loaded. Check the provider and ID, then retry.') from None
    if len(_cache) >= 32:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (monotonic(), deepcopy(fresh))
    return fresh


def reconcile_seasons(row, fresh, identity_changed):
    """Preserve season/episode primary keys and all file, request and job relationships."""
    from media_manager.tv.models import Season, Episode
    from uuid import uuid4
    if identity_changed:
        for season in row.seasons:
            season.external_id = 0
            for episode in season.episodes:
                episode.external_id = 0
    for incoming in fresh.seasons:
        season = next((s for s in row.seasons if s.number == incoming.number), None)
        if season is None:
            season = Season(id=uuid4(), number=incoming.number, external_id=incoming.external_id, name=incoming.name, overview=incoming.overview)
            row.seasons.append(season)
        season.external_id = incoming.external_id or season.external_id
        season.name = incoming.name
        season.overview = incoming.overview
        for item in incoming.episodes:
            episode = next((e for e in season.episodes if e.number == item.number), None)
            if episode is None:
                episode = Episode(id=uuid4(), number=item.number, external_id=item.external_id, title=item.title, air_date=item.air_date)
                season.episodes.append(episode)
            episode.external_id = item.external_id or episode.external_id
            episode.title = item.title
            episode.air_date = item.air_date


@router.get('/{kind}/{media_id}/preview')
def preview(kind: Literal['tv', 'movies'], media_id: UUID, db: DbSessionDependency, provider: Literal['tmdb', 'tvdb'], external_id: int = Query(gt=0)):
    row = db.get(model_type(kind), media_id)
    if row is None:
        raise HTTPException(404, 'Title not found.')
    fresh = load_metadata(kind, provider, external_id, row.original_language)
    return {'name': fresh.name, 'year': fresh.year, 'overview': fresh.overview, 'provider': provider, 'external_id': external_id}


@router.put('/{kind}/{media_id}')
def edit_metadata(kind: Literal['tv', 'movies'], media_id: UUID, body: MetadataEdit, db: DbSessionDependency):
    from media_manager.tv.schemas import Show as ShowSchema
    from media_manager.movies.schemas import Movie as MovieSchema
    cls = model_type(kind)
    row = db.get(cls, media_id)
    if row is None:
        raise HTTPException(404, 'Title not found.')
    changed = (row.metadata_provider, row.external_id) != (body.provider, body.external_id)
    if changed and not body.confirm_identity_change:
        raise HTTPException(400, 'Changing the metadata identity requires confirmation.')
    # Provider access finishes before taking a write lock; failed lookups leave the database intact.
    fresh = load_metadata(kind, body.provider, body.external_id, row.original_language) if changed or body.refresh_metadata else None
    row = db.scalars(select(cls).where(cls.id == media_id).with_for_update().execution_options(populate_existing=True)).one()
    if (row.metadata_provider, row.external_id) != (body.previous_provider, body.previous_external_id):
        raise HTTPException(409, 'The metadata identity has changed. Reload this page before editing.')
    duplicate = db.scalar(select(cls.id).where(cls.metadata_provider == body.provider, cls.external_id == body.external_id, cls.id != media_id))
    if duplicate:
        raise HTTPException(409, 'This provider ID already belongs to another title. No records were merged.')
    row.metadata_provider = body.provider
    row.external_id = body.external_id
    row.name = body.name.strip()
    if not row.name:
        raise HTTPException(422, 'A title is required.')
    row.year = body.year
    row.overview = body.overview
    if fresh:
        row.imdb_id = fresh.imdb_id
        if kind == 'tv':
            row.ended = fresh.ended
            reconcile_seasons(row, fresh, changed)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This provider ID already belongs to another title. No records were merged.') from None
    warning = None
    if fresh:
        try:
            api = get_metadata_provider(body.provider)
            model = (ShowSchema if kind == 'tv' else MovieSchema).model_validate(row)
            ok = api.download_show_poster_image(show=model) if kind == 'tv' else api.download_movie_poster_image(movie=model)
            if not ok:
                warning = 'Details saved, but the provider did not supply a poster.'
        except Exception:
            warning = 'Details saved, but the poster could not be refreshed.'
    return {'saved': True, 'id': str(row.id), 'warning': warning}
