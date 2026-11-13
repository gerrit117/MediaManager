from fastapi import BackgroundTasks
from pathlib import Path
from typing import Literal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from media_manager.auth.db import User
from media_manager.auth.schemas import UserRead
from media_manager.auth.users import current_active_user, current_superuser
from media_manager.config import LibraryItem, MediaManagerConfig
from media_manager.exceptions import MediaAlreadyExistsError, NotFoundError
from media_manager.indexer.schemas import (
    IndexerQueryResult,
    IndexerQueryResultId,
)
from media_manager.metadataProvider.dependencies import metadata_provider_dep
from media_manager.metadataProvider.schemas import MetaDataProviderSearchResult
from media_manager.schemas import MediaImportSuggestion
from media_manager.torrent.schemas import Torrent
from media_manager.torrent.utils import get_importable_media_directories
from media_manager.tv import log
from media_manager.tv.dependencies import (
    season_dep,
    show_dep,
    tv_service_dep,
)
from media_manager.tv.schemas import (
    CreateSeasonRequest,
    PublicSeasonFile,
    PublicShow,
    RichSeasonRequest,
    RichShowTorrent,
    Season,
    SeasonRequest,
    SeasonRequestId,
    Show,
    ShowId,
    UpdateSeasonRequest,
)

router = APIRouter()

# -----------------------------------------------------------------------------
# METADATA & SEARCH
# -----------------------------------------------------------------------------


@router.get(
    "/search",
    dependencies=[Depends(current_active_user)],
)
def search_metadata_providers_for_a_show(
    tv_service: tv_service_dep, query: str, metadata_provider: metadata_provider_dep
) -> list[MetaDataProviderSearchResult]:
    """
    Search for a show on the configured metadata provider.
    """
    return tv_service.search_for_show(query=query, metadata_provider=metadata_provider)


@router.get(
    "/recommended",
    dependencies=[Depends(current_active_user)],
)
def get_recommended_shows(
    tv_service: tv_service_dep, metadata_provider: metadata_provider_dep
) -> list[MetaDataProviderSearchResult]:
    """
    Get a list of recommended/popular shows from the metadata provider.
    """
    from media_manager.discovery import discover
    return discover('tv',tv_service.tv_repository.db,mode='trending',window='week',page=1,region='DE',language='de',provider_id=None,company_id=None,genre_id=None,min_votes=100)['results']


# -----------------------------------------------------------------------------
# IMPORTING
# -----------------------------------------------------------------------------


@router.get(
    "/importable",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_superuser)],
)
def get_all_importable_shows(
    tv_service: tv_service_dep, metadata_provider: metadata_provider_dep, discover_only: bool = False
) -> list[MediaImportSuggestion]:
    """
    Get a list of unknown shows that were detected in the TV directory and are importable.
    """
    return tv_service.get_importable_tv_shows(metadata_provider=metadata_provider, discover_only=discover_only)


@router.post(
    "/importable/{show_id}",
    dependencies=[Depends(current_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def import_detected_show(
    tv_service: tv_service_dep, tv_show: show_dep, directory: str,
    mode: Literal["catalogue", "reorganize"] = "catalogue",
) -> None:
    """
    Import a detected show from the specified directory into the library.
    """
    source_directory = Path(directory)
    if source_directory.is_symlink():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Symlink directories cannot be imported")
    if source_directory not in get_importable_media_directories(
        MediaManagerConfig().misc.tv_directory
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such directory")
    if mode == "catalogue":
        if not tv_service.catalogue_existing_tv_show(tv_show, source_directory):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No recognizable episode files found (S01E01 or 1x01)")
    else:
        tv_service.import_existing_tv_show(tv_show, source_directory)


# -----------------------------------------------------------------------------
# SHOWS
# -----------------------------------------------------------------------------


@router.get(
    "/shows",
    dependencies=[Depends(current_active_user)],
)
def get_all_shows(tv_service: tv_service_dep) -> list[Show]:
    """
    Get all shows in the library.
    """
    return tv_service.get_all_shows()


@router.post(
    "/shows",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(current_superuser)],
    responses={
        status.HTTP_201_CREATED: {
            "model": Show,
            "description": "Successfully created show",
        }
    },
)
def add_a_show(
    tv_service: tv_service_dep,
    metadata_provider: metadata_provider_dep,
    show_id: int,
    tasks: BackgroundTasks,
    language: str | None = None,
    search_missing: bool = False,
) -> Show:
    """
    Add a new show to the library.
    """
    try:
        show = tv_service.add_show(
            external_id=show_id,
            metadata_provider=metadata_provider,
            language=language,
        )
    except MediaAlreadyExistsError:
        show = tv_service.get_show_by_external_id(
            show_id, metadata_provider=metadata_provider.name
        )
        if not show:
            raise NotFoundError from MediaAlreadyExistsError
    if search_missing:
        from media_manager.tv.backfill import start

        try:
            start(show.id, None, tasks)
        except HTTPException as error:
            if error.status_code != 409:
                raise
    return show


@router.get(
    "/shows/torrents",
    dependencies=[Depends(current_active_user)],
)
def get_shows_with_torrents(tv_service: tv_service_dep) -> list[RichShowTorrent]:
    """
    Get all shows that are associated with torrents.
    """
    return tv_service.get_all_shows_with_torrents()


@router.get(
    "/shows/libraries",
    dependencies=[Depends(current_active_user)],
)
def get_available_libraries() -> list[LibraryItem]:
    """
    Get available TV libraries from configuration.
    """
    return MediaManagerConfig().misc.tv_libraries


# -----------------------------------------------------------------------------
# SHOWS - INDIVIDUAL
# -----------------------------------------------------------------------------


@router.get(
    "/shows/{show_id}",
    dependencies=[Depends(current_active_user)],
)
def get_a_show(show: show_dep, tv_service: tv_service_dep) -> PublicShow:
    """
    Get details for a specific show.
    """
    return tv_service.get_public_show_by_id(show=show)


@router.delete(
    "/shows/{show_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(current_superuser)],
)
def delete_a_show(
    tv_service: tv_service_dep,
    show: show_dep,
    delete_files_on_disk: bool = False,
    delete_torrents: bool = False,
) -> None:
    """
    Delete a show from the library.
    """
    tv_service.delete_show(
        show=show,
        delete_files_on_disk=delete_files_on_disk,
        delete_torrents=delete_torrents,
    )


@router.post(
    "/shows/{show_id}/metadata",
    dependencies=[Depends(current_active_user)],
)
def update_shows_metadata(
    show: show_dep, tv_service: tv_service_dep, metadata_provider: metadata_provider_dep
) -> PublicShow:
    """
    Update a show's metadata from the provider.
    """
    tv_service.update_show_metadata(db_show=show, metadata_provider=metadata_provider)
    return tv_service.get_public_show_by_id(show=show)


@router.post(
    "/shows/{show_id}/continuousDownload",
    dependencies=[Depends(current_superuser)],
)
def set_continuous_download(
    show: show_dep, tv_service: tv_service_dep, continuous_download: bool,
    tasks: BackgroundTasks, include_history: bool | None = None,
) -> PublicShow:
    """
    Toggle monitoring of newly aired episodes and seasons from activation.
    """
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from media_manager.tv.backfill import start
    from media_manager.tv.models import Show as StoredShow

    db = tv_service.tv_repository.db
    row = db.get(StoredShow, show.id)
    was_enabled = row.continuous_download
    had_history = row.monitor_from == date.min
    row.continuous_download = continuous_download
    if include_history is True:
        row.monitor_from = date.min
    elif include_history is False and (had_history or not was_enabled):
        row.monitor_from = datetime.now(ZoneInfo("Europe/Berlin")).date()
    db.commit()
    if continuous_download and include_history and (not had_history or not was_enabled):
        try:
            start(show.id, None, tasks)
        except HTTPException as error:
            if error.status_code != 409:
                raise
    return tv_service.get_public_show_by_id(show=tv_service.get_show_by_id(show.id))


@router.post(
    "/shows/{show_id}/library",
    dependencies=[Depends(current_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def set_library(
    show: show_dep,
    tv_service: tv_service_dep,
    library: str,
) -> None:
    """
    Set the library path for a Show.
    """
    tv_service.set_show_library(show=show, library=library)
    return


@router.get(
    "/shows/{show_id}/torrents",
    dependencies=[Depends(current_active_user)],
)
def get_a_shows_torrents(show: show_dep, tv_service: tv_service_dep) -> RichShowTorrent:
    """
    Get torrents associated with a specific show.
    """
    return tv_service.get_torrents_for_show(show=show)


# -----------------------------------------------------------------------------
# SEASONS - REQUESTS
# -----------------------------------------------------------------------------


@router.get(
    "/seasons/requests",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_active_user)],
)
def get_season_requests(tv_service: tv_service_dep,user:Annotated[User,Depends(current_active_user)]) -> list[RichSeasonRequest]:
    """
    Get all season requests.
    """
    return [r for r in tv_service.get_all_season_requests() if user.is_superuser or (r.requested_by and r.requested_by.id==user.id)]


@router.post("/seasons/requests", status_code=status.HTTP_204_NO_CONTENT)
def request_a_season(
    user: Annotated[User, Depends(current_active_user)],
    season_request: CreateSeasonRequest,
    tv_service: tv_service_dep,
    tasks: BackgroundTasks,
) -> None:
    """
    Create a new season request.
    """
    request: SeasonRequest = SeasonRequest.model_validate(season_request)
    request.requested_by = UserRead.model_validate(user)
    if user.is_superuser:
        request.authorized = True
        request.authorized_by = UserRead.model_validate(user)
    tv_service.add_season_request(request)
    from media_manager.auth.mail import notify_admins
    # Durable request observer handles per-account notifications.
    return


@router.put("/seasons/requests", status_code=status.HTTP_204_NO_CONTENT)
def update_request(
    tv_service: tv_service_dep,
    user: Annotated[User, Depends(current_active_user)],
    season_request: UpdateSeasonRequest,
) -> None:
    """
    Update an existing season request.
    """
    request = tv_service.get_season_request_by_id(season_request_id=season_request.id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if not user.is_superuser and (not request.requested_by or request.requested_by.id != user.id):
        raise HTTPException(status_code=403, detail="Not authorized to edit this request")
    request.min_quality = season_request.min_quality
    request.wanted_quality = season_request.wanted_quality
    tv_service.update_season_request(season_request=request)
    return


@router.patch(
    "/seasons/requests/{season_request_id}", status_code=status.HTTP_204_NO_CONTENT
)
def authorize_request(
    tv_service: tv_service_dep,
    user: Annotated[User, Depends(current_superuser)],
    season_request_id: SeasonRequestId,
    authorized_status: bool = False,
) -> None:
    """
    Authorize or de-authorize a season request.
    """
    season_request = tv_service.get_season_request_by_id(
        season_request_id=season_request_id
    )
    if not season_request:
        raise NotFoundError
    season_request.authorized_by = UserRead.model_validate(user)
    season_request.authorized = authorized_status
    if not authorized_status:
        season_request.authorized_by = None
    tv_service.update_season_request(season_request=season_request)


@router.delete(
    "/seasons/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_season_request(
    tv_service: tv_service_dep,
    user: Annotated[User, Depends(current_active_user)],
    request_id: SeasonRequestId,
) -> None:
    """
    Delete a season request.
    """
    request = tv_service.get_season_request_by_id(season_request_id=request_id)
    if user.is_superuser or request.requested_by.id == user.id:
        tv_service.delete_season_request(season_request_id=request_id)
        log.info(f"User {user.id} deleted season request {request_id}.")
        return
    log.warning(
        f"User {user.id} tried to delete season request {request_id} but is not authorized."
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to delete this request",
    )


# -----------------------------------------------------------------------------
# SEASONS
# -----------------------------------------------------------------------------


@router.get(
    "/seasons/{season_id}",
    dependencies=[Depends(current_active_user)],
)
def get_season(season: season_dep) -> Season:
    """
    Get details for a specific season.
    """
    return season


@router.get(
    "/seasons/{season_id}/files",
    dependencies=[Depends(current_active_user)],
)
def get_season_files(
    season: season_dep, tv_service: tv_service_dep
) -> list[PublicSeasonFile]:
    """
    Get files associated with a specific season.
    """
    return tv_service.get_public_season_files_by_season_id(season=season)


# -----------------------------------------------------------------------------
# TORRENTS
# -----------------------------------------------------------------------------


@router.get(
    "/torrents",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_superuser)],
)
def get_torrents_for_a_season(
    tv_service: tv_service_dep,
    show_id: ShowId,
    season_number: int = 1,
    search_query_override: str | None = None,
) -> list[IndexerQueryResult]:
    """
    Search for torrents for a specific season of a show.
    Default season_number is 1 because it often returns multi-season torrents.
    """
    return tv_service.get_all_available_torrents_for_a_season(
        season_number=season_number,
        show_id=show_id,
        search_query_override=search_query_override,
    )


@router.post(
    "/torrents",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_superuser)],
)
def download_a_torrent(
    tv_service: tv_service_dep,
    public_indexer_result_id: IndexerQueryResultId,
    show_id: ShowId,
    override_file_path_suffix: str = "",
    replace_existing: bool = True,
    override_lock: bool = False,
) -> Torrent:
    """
    Trigger a download for a specific torrent.
    """
    return tv_service.download_torrent(
        public_indexer_result_id=public_indexer_result_id,
        show_id=show_id,
        override_show_file_path_suffix=override_file_path_suffix,
        replace_existing=replace_existing,override_lock=override_lock,
    )


# -----------------------------------------------------------------------------
# STATISTICS
# -----------------------------------------------------------------------------


@router.get(
    "/episodes/count",
    status_code=status.HTTP_200_OK,
    description="Total number of episodes downloaded",
    dependencies=[Depends(current_active_user)],
)
def get_total_count_of_downloaded_episodes(tv_service: tv_service_dep) -> int:
    """
    Get the total count of downloaded episodes across all shows.
    """
    return tv_service.get_total_downloaded_episoded_count()


@router.get("/shows/{show_id}/backfill", dependencies=[Depends(current_superuser)])
def get_backfill_status(tv_show: show_dep) -> dict:
    from media_manager.tv.backfill import status as backfill_status

    return backfill_status(tv_show.id)


@router.post("/shows/{show_id}/backfill", status_code=202, dependencies=[Depends(current_superuser)])
def start_backfill(
    tv_show: show_dep, tasks: BackgroundTasks,
    season_number: int | None = None, episode_number: int | None = None,
) -> dict:
    from media_manager.tv.backfill import start

    if season_number is not None or episode_number is not None:
        season = next(
            (item for item in tv_show.seasons if item.number == season_number and item.number > 0),
            None,
        )
        if season is None:
            raise HTTPException(422, "Season not found.")
        if episode_number is not None and not any(
            episode.number == episode_number for episode in season.episodes
        ):
            raise HTTPException(422, "Episode not found.")
    start(tv_show.id, season_number, tasks, episode_number)
    return {"status": "running"}


@router.get('/shows/{show_id}/monitor', dependencies=[Depends(current_active_user)])
def get_episode_monitor_status(tv_service: tv_service_dep, tv_show: show_dep):
    from sqlalchemy import select
    from media_manager.tv.models import EpisodeDownload, Episode, Season
    jobs=tv_service.tv_repository.db.scalars(select(EpisodeDownload).join(Episode).join(Season).where(Season.show_id==tv_show.id)).all()
    from datetime import date
    include_history = tv_show.monitor_from == date.min
    return {'enabled':tv_show.continuous_download,'since':None if include_history else tv_show.monitor_from,
            'include_history':include_history,
            'submitted':sum(j.status=='submitted' for j in jobs),
            'imported':sum(j.status=='imported' for j in jobs),
            'uncertain':sum(j.status in {'submitting','uncertain'} for j in jobs),
            'missing_dates':sum(e.air_date is None for s in tv_show.seasons if s.number>0 for e in s.episodes)}
