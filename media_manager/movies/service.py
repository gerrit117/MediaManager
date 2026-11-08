import re
import shutil
from pathlib import Path
from media_manager.library import video_files, catalogue_suffix, episode_numbers
from typing import overload

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from media_manager.config import MediaManagerConfig
from media_manager.database import SessionLocal, get_session
from media_manager.exceptions import InvalidConfigError, NotFoundError, RenameError
from media_manager.indexer.repository import IndexerRepository
from media_manager.indexer.schemas import IndexerQueryResult, IndexerQueryResultId
from media_manager.indexer.service import IndexerService
from media_manager.indexer.utils import evaluate_indexer_query_results
from media_manager.metadataProvider.abstract_metadata_provider import (
    AbstractMetadataProvider,
)
from media_manager.metadataProvider.schemas import MetaDataProviderSearchResult
from media_manager.metadataProvider.tmdb import TmdbMetadataProvider
from media_manager.metadataProvider.tvdb import TvdbMetadataProvider
from media_manager.movies import log
from media_manager.movies.repository import MovieRepository
from media_manager.movies.schemas import (
    Movie,
    MovieFile,
    MovieId,
    MovieRequest,
    MovieRequestId,
    PublicMovie,
    PublicMovieFile,
    RichMovieRequest,
    RichMovieTorrent,
)
from media_manager.notification.repository import NotificationRepository
from media_manager.notification.service import NotificationService
from media_manager.schemas import MediaImportSuggestion
from media_manager.torrent.repository import TorrentRepository
from media_manager.torrent.schemas import (
    Quality,
    QualityStrings,
    Torrent,
    TorrentStatus,
)
from media_manager.torrent.service import TorrentService
from media_manager.torrent.utils import (
    validate_file_path_suffix,
    extract_external_id_from_string,
    get_files_for_import,
    get_importable_media_directories,
    import_file,
    remove_special_characters,
    remove_special_chars_and_parentheses,
)


class MovieService:
    def __init__(
        self,
        movie_repository: MovieRepository,
        torrent_service: TorrentService,
        indexer_service: IndexerService,
        notification_service: NotificationService,
    ) -> None:
        self.movie_repository = movie_repository
        self.torrent_service = torrent_service
        self.indexer_service = indexer_service
        self.notification_service = notification_service

    def add_movie(
        self,
        external_id: int,
        metadata_provider: AbstractMetadataProvider,
        language: str | None = None,
        request_only: bool = False,
    ) -> Movie:
        """
        Add a new movie to the database.

        :param external_id: The ID of the movie in the metadata provider's system.
        :param metadata_provider: The name of the metadata provider.
        :param language: Optional language code (ISO 639-1) to fetch metadata in.
        """
        try:
            existing=self.movie_repository.get_movie_by_external_id(external_id,metadata_provider.name)
            if not request_only:
                from media_manager.movies.models import Movie as StoredMovie
                self.movie_repository.db.get(StoredMovie,existing.id).request_only=False
                self.movie_repository.db.commit()
            return existing
        except NotFoundError:pass
        movie_with_metadata = metadata_provider.get_movie_metadata(
            movie_id=external_id, language=language
        )
        if not movie_with_metadata:
            raise NotFoundError

        movie_with_metadata.request_only=request_only
        saved_movie = self.movie_repository.save_movie(movie=movie_with_metadata)
        metadata_provider.download_movie_poster_image(movie=saved_movie)
        return saved_movie

    def add_movie_request(self, movie_request: MovieRequest) -> MovieRequest:
        """
        Add a new movie request.

        :param movie_request: The movie request to add.
        :return: The added movie request.
        """
        return self.movie_repository.add_movie_request(movie_request=movie_request)

    def get_movie_request_by_id(self, movie_request_id: MovieRequestId) -> MovieRequest:
        """
        Get a movie request by its ID.

        :param movie_request_id: The ID of the movie request.
        :return: The movie request or None if not found.
        """
        return self.movie_repository.get_movie_request(
            movie_request_id=movie_request_id
        )

    def update_movie_request(self, movie_request: MovieRequest) -> MovieRequest:
        """
        Update an existing movie request.

        :param movie_request: The movie request to update.
        :return: The updated movie request.
        """
        self.movie_repository.delete_movie_request(movie_request_id=movie_request.id)
        return self.movie_repository.add_movie_request(movie_request=movie_request)

    def delete_movie_request(self, movie_request_id: MovieRequestId) -> None:
        """
        Delete a movie request by its ID.

        :param movie_request_id: The ID of the movie request to delete.
        """
        self.movie_repository.delete_movie_request(movie_request_id=movie_request_id)

    def delete_movie(
        self,
        movie: Movie,
        delete_files_on_disk: bool = False,
        delete_torrents: bool = False,
    ) -> None:
        """
        Delete a movie from the database, optionally deleting files and torrents.

        :param movie: The movie to delete.
        :param delete_files_on_disk: Whether to delete the movie's files from disk.
        :param delete_torrents: Whether to delete associated torrents from the torrent client.
        """
        if delete_files_on_disk or delete_torrents:
            if delete_files_on_disk:
                # Get the movie's directory path
                movie_dir = self.get_movie_root_path(movie=movie)

                if movie_dir.exists() and movie_dir.is_dir():
                    try:
                        shutil.rmtree(movie_dir)
                        log.info(f"Deleted movie directory: {movie_dir}")
                    except OSError:
                        log.exception(f"Deleting movie directory: {movie_dir}")

            if delete_torrents:
                # Get all torrents associated with this movie
                movie_torrents = self.movie_repository.get_torrents_by_movie_id(
                    movie_id=movie.id
                )

                for movie_torrent in movie_torrents:
                    torrent = self.torrent_service.get_torrent_by_id(
                        torrent_id=movie_torrent.torrent_id
                    )
                    try:
                        self.torrent_service.cancel_download(
                            torrent=torrent, delete_files=True
                        )
                        log.info(f"Deleted torrent: {torrent.torrent_title}")
                    except Exception:
                        log.warning(
                            f"Failed to delete torrent {torrent.hash}", exc_info=True
                        )

        # Delete from database
        self.movie_repository.delete_movie(movie_id=movie.id)

    def get_public_movie_files(self, movie: Movie) -> list[PublicMovieFile]:
        """
        Get all public movie files for a given movie.

        :param movie: The movie object.
        :return: A list of public movie files.
        """
        movie_files = self.movie_repository.get_movie_files_by_movie_id(
            movie_id=movie.id
        )
        public_movie_files = [PublicMovieFile.model_validate(x) for x in movie_files]
        result = []
        for movie_file in public_movie_files:
            movie_file.imported = self.movie_file_exists_on_file(movie_file=movie_file)
            result.append(movie_file)
        return result

    @overload
    def check_if_movie_exists(
        self, *, external_id: int, metadata_provider: str
    ) -> bool:
        """
        Check if a movie exists in the database.

        :param external_id: The external ID of the movie.
        :param metadata_provider: The metadata provider.
        :return: True if the movie exists, False otherwise.
        """

    @overload
    def check_if_movie_exists(self, *, movie_id: MovieId) -> bool:
        """
        Check if a movie exists in the database.

        :param movie_id: The ID of the movie.
        :return: True if the movie exists, False otherwise.
        """

    def check_if_movie_exists(
        self,
        *,
        external_id=None,
        metadata_provider=None,
        movie_id=None,
    ) -> bool:
        """
        Check if a movie exists in the database.

        :param external_id: The external ID of the movie.
        :param metadata_provider: The metadata provider.
        :param movie_id: The ID of the movie.
        :return: True if the movie exists, False otherwise.
        :raises ValueError: If neither external ID and metadata provider nor movie ID are provided.
        """

        if not (external_id is None or metadata_provider is None):
            try:
                found=self.movie_repository.get_movie_by_external_id(
                    external_id=external_id, metadata_provider=metadata_provider
                )
            except NotFoundError:
                return False
        elif movie_id is not None:
            try:
                found=self.movie_repository.get_movie_by_id(movie_id=movie_id)
            except NotFoundError:
                return False
        else:
            msg = "Use one of the provided overloads for this function!"
            raise ValueError(msg)

        return not found.request_only

    def get_all_available_torrents_for_movie(
        self, movie: Movie, search_query_override: str | None = None
    ) -> list[IndexerQueryResult]:
        """
        Get all available torrents for a given movie.

        :param movie: The movie object.
        :param search_query_override: Optional override for the search query.
        :return: A list of indexer query results.
        """
        if search_query_override:
            torrents = self.indexer_service.search(
                query=search_query_override, is_tv=False
            )
        else:
            torrents = self.indexer_service.search_movie(movie=movie)

        return evaluate_indexer_query_results(
            is_tv=False, query_results=torrents, media=movie
        )

    def get_all_movies(self) -> list[Movie]:
        """
        Get all movies.

        :return: A list of all movies.
        """
        return self.movie_repository.get_movies()

    def search_for_movie(
        self, query: str, metadata_provider: AbstractMetadataProvider
    ) -> list[MetaDataProviderSearchResult]:
        """
        Search for movies using a given query.

        :param query: The search query.
        :param metadata_provider: The metadata provider to search.
        :return: A list of metadata provider movie search results.
        """
        results = metadata_provider.search_movie(query)
        for result in results:
            if self.check_if_movie_exists(
                external_id=result.external_id, metadata_provider=metadata_provider.name
            ):
                result.added = True

                # Fetch the internal movie ID.
                try:
                    movie = self.movie_repository.get_movie_by_external_id(
                        external_id=result.external_id,
                        metadata_provider=metadata_provider.name,
                    )
                    result.id = movie.id
                except Exception:
                    log.error(
                        f"Unable to find internal movie ID for {result.external_id} on {metadata_provider.name}"
                    )
        return results


    def get_public_movie_by_id(self, movie: Movie) -> PublicMovie:
        """
        Get a public movie from a Movie object.

        :param movie: The movie object.
        :return: A public movie.
        """
        torrents = self.get_torrents_for_movie(movie=movie).torrents
        public_movie = PublicMovie.model_validate(movie)
        public_movie.downloaded = self.is_movie_downloaded(movie=movie)
        public_movie.torrents = torrents
        return public_movie

    def get_movie_by_id(self, movie_id: MovieId) -> Movie:
        """
        Get a movie by its ID.

        :param movie_id: The ID of the movie.
        :return: The movie.
        """
        return self.movie_repository.get_movie_by_id(movie_id=movie_id)

    def is_movie_downloaded(self, movie: Movie) -> bool:
        """
        Check if a movie is downloaded.

        :param movie: The movie object.
        :return: True if the movie is downloaded, False otherwise.
        """
        movie_files = self.movie_repository.get_movie_files_by_movie_id(
            movie_id=movie.id
        )
        for movie_file in movie_files:
            if self.movie_file_exists_on_file(movie_file=movie_file):
                return True
        return False

    def movie_file_exists_on_file(self, movie_file: MovieFile) -> bool:
        """
        Check if a movie file exists on the filesystem.

        :param movie_file: The movie file to check.
        :return: True if the file exists, False otherwise.
        """
        if movie_file.source_files is not None:
            return any(Path(p).is_file() for p in movie_file.source_files)
        if movie_file.torrent_id is None:
            return True
        torrent_file = self.torrent_service.get_torrent_by_id(
            torrent_id=movie_file.torrent_id
        )
        if torrent_file.imported:
            return True
        return False

    def get_movie_by_external_id(
        self, external_id: int, metadata_provider: str
    ) -> Movie | None:
        """
        Get a movie by its external ID and metadata provider.

        :param external_id: The external ID of the movie.
        :param metadata_provider: The metadata provider.
        :return: The movie or None if not found.
        """
        return self.movie_repository.get_movie_by_external_id(
            external_id=external_id, metadata_provider=metadata_provider
        )

    def get_all_movie_requests(self) -> list[RichMovieRequest]:
        """
        Get all movie requests.

        :return: A list of rich movie requests.
        """
        return self.movie_repository.get_movie_requests()

    def set_movie_library(self, movie: Movie, library: str) -> None:
        self.movie_repository.set_movie_library(movie_id=movie.id, library=library)

    def get_torrents_for_movie(self, movie: Movie) -> RichMovieTorrent:
        """
        Get torrents for a given movie.

        :param movie: The movie.
        :return: A rich movie torrent.
        """
        movie_torrents = self.movie_repository.get_torrents_by_movie_id(
            movie_id=movie.id
        )
        return RichMovieTorrent(
            movie_id=movie.id,
            name=movie.name,
            year=movie.year,
            metadata_provider=movie.metadata_provider,
            torrents=movie_torrents,
        )

    def get_all_movies_with_torrents(self) -> list[RichMovieTorrent]:
        """
        Get all movies with torrents.

        :return: A list of rich movie torrents.
        """
        movies = self.movie_repository.get_all_movies_with_torrents()
        return [self.get_torrents_for_movie(movie=movie) for movie in movies]

    def download_torrent(
        self,
        public_indexer_result_id: IndexerQueryResultId,
        movie: Movie,
        override_movie_file_path_suffix: str = "",
    ) -> Torrent:
        """
        Download a torrent for a given indexer result and movie.

        :param public_indexer_result_id: The ID of the indexer result.
        :param movie: The movie object.
        :param override_movie_file_path_suffix: Optional override for the file path suffix.
        :return: The downloaded torrent.
        """
        override_movie_file_path_suffix = validate_file_path_suffix(override_movie_file_path_suffix)
        indexer_result = self.indexer_service.get_result(
            result_id=public_indexer_result_id
        )
        if MediaManagerConfig().indexers.release_policy.enabled:
            from fastapi import HTTPException
            media = movie
            if not evaluate_indexer_query_results([indexer_result],media,is_tv=False):
                raise HTTPException(409,'Release is excluded by the configured scoring rules.')
        from media_manager.release_policy import validate_selection
        if MediaManagerConfig().indexers.release_policy.enabled:
            validate_selection(indexer_result, self.get_all_available_torrents_for_movie(movie))
        movie_torrent = self.torrent_service.download(indexer_result=indexer_result)
        self.torrent_service.pause_download(torrent=movie_torrent)
        movie_file = MovieFile(
            movie_id=movie.id,
            quality=indexer_result.quality,
            torrent_id=movie_torrent.id,
            file_path_suffix=override_movie_file_path_suffix,
        )
        try:
            self.movie_repository.add_movie_file(movie_file=movie_file)
        except IntegrityError:
            log.warning(
                f"Movie file for movie {movie.name} and torrent {movie_torrent.title} already exists"
            )
            self.torrent_service.cancel_download(
                torrent=movie_torrent, delete_files=True
            )
            raise
        else:
            log.info(
                f"Added movie file for movie {movie.name} and torrent {movie_torrent.title}"
            )
            self.torrent_service.resume_download(torrent=movie_torrent)
        return movie_torrent

    def download_approved_movie_request(
        self, movie_request: MovieRequest, movie: Movie
    ) -> bool:
        """
        Download an approved movie request.

        :param movie_request: The movie request to download.
        :param movie: The Movie object.
        :return: True if the download was successful, False otherwise.
        :raises ValueError: If the movie request is not authorized.
        """
        if not movie_request.authorized:
            msg = "Movie request is not authorized"
            raise ValueError(msg)

        log.info(f"Downloading approved movie request {movie_request.id}")

        from media_manager.movies.models import MovieFile as StoredFile
        from media_manager.torrent.models import Torrent as StoredJob
        from sqlalchemy import select
        db=self.movie_repository.db
        records=list(db.scalars(select(StoredFile).where(StoredFile.movie_id==movie.id)))
        previous_jobs=[db.get(StoredJob,r.torrent_id) for r in records if r.torrent_id]
        if any(j and not j.imported for j in previous_jobs):return False
        torrents = self.get_all_available_torrents_for_movie(movie=movie)
        available_torrents: list[IndexerQueryResult] = []

        for torrent in torrents:
            if (
                (torrent.quality.value < movie_request.wanted_quality.value)
                or (torrent.quality.value > movie_request.min_quality.value)
                or (not torrent.usenet and torrent.seeders < 3)
            ):
                log.debug(
                    f"Skipping torrent {torrent.title} with quality {torrent.quality} for movie {movie.id}, because it does not match the requested quality {movie_request.wanted_quality}"
                )
            else:
                available_torrents.append(torrent)
                log.debug(
                    f"Taking torrent {torrent.title} with quality {torrent.quality} for movie {movie.id} into consideration"
                )

        if len(available_torrents) == 0:
            log.warning(
                f"No torrents found for movie request {movie_request.id} with quality between {QualityStrings[movie_request.min_quality.name]} and {QualityStrings[movie_request.wanted_quality.name]}"
            )
            return False

        from media_manager.release_policy import allowed_results
        available_torrents = allowed_results(available_torrents,available_only=True)
        if not available_torrents:return False
        from media_manager.release_policy import rank
        candidate=available_torrents[0]
        for previous in previous_jobs:
            if previous and previous.imported:
                old=IndexerQueryResult(title=previous.title,download_url='',seeders=3,flags=[],size=0,usenet=previous.usenet,age=0,indexer=None)
                if rank(candidate)[:2]<=rank(old)[:2]:return False

        torrent = self.torrent_service.download(indexer_result=available_torrents[0])
        movie_file = MovieFile(
            movie_id=movie.id,
            quality=torrent.quality,
            torrent_id=torrent.id,
            file_path_suffix=QualityStrings[torrent.quality.name].value.upper(),
        )
        try:
            self.movie_repository.add_movie_file(movie_file=movie_file)
        except IntegrityError:
            log.warning(
                f"Movie file for movie {movie.name} and torrent {torrent.title} already exists"
            )
        self.delete_movie_request(movie_request.id)
        return True

    def get_movie_root_path(self, movie: Movie) -> Path:
        misc_config = MediaManagerConfig().misc
        movie_file_path = (
            misc_config.movie_directory
            / f"{remove_special_characters(movie.name)} ({movie.year}) [{movie.metadata_provider}id-{movie.external_id}]"
        )
        log.debug(
            f"Movie {movie.name} without special characters: {remove_special_characters(movie.name)}"
        )
        if movie.library != "Default":
            for library in misc_config.movie_libraries:
                if library.name == movie.library:
                    log.debug(f"Using library {library.name} for movie {movie.name}")
                    return (
                        Path(library.path)
                        / f"{remove_special_characters(movie.name)} ({movie.year}) [{movie.metadata_provider}id-{movie.external_id}]"
                    )
            else:
                log.warning(
                    f"Library {movie.library} not found in config, using default library"
                )
        return movie_file_path

    def import_movie(
        self,
        movie: Movie,
        video_files: list[Path],
        subtitle_files: list[Path],
        file_path_suffix: str = "",
    ) -> bool:
        file_path_suffix = validate_file_path_suffix(file_path_suffix)
        movie_file_name = f"{remove_special_characters(movie.name)} ({movie.year})"
        movie_root_path = self.get_movie_root_path(movie=movie)
        success: bool = False
        if file_path_suffix != "":
            movie_file_name += f" - {file_path_suffix}"

        try:
            movie_root_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            log.exception("Failed to create directory {movie_root_path}")
            return False

        # import movie video
        if video_files:
            target_video_file = (
                movie_root_path / f"{movie_file_name}{video_files[0].suffix}"
            )
            import_file(target_file=target_video_file, source_file=video_files[0])
            success = True

        # import subtitles
        for subtitle_file in subtitle_files:
            language_code_match = re.search(
                r"[. ]([a-z]{2})\.srt$", subtitle_file.name, re.IGNORECASE
            )
            if not language_code_match:
                log.warning(
                    f"Subtitle file {subtitle_file.name} does not match expected format, can't extract language code, skipping."
                )
                continue
            language_code = language_code_match.group(1)
            target_subtitle_file = (
                movie_root_path / f"{movie_file_name}.{language_code}.srt"
            )
            import_file(target_file=target_subtitle_file, source_file=subtitle_file)

        return success

    def import_torrent_files(self, torrent: Torrent, movie: Movie) -> None:
        """
        Organizes files from a torrent into the movie directory structure.
        :param torrent: The Torrent object
        :param movie: The Movie object
        """

        video_files, subtitle_files, _all_files = get_files_for_import(torrent=torrent)

        if len(video_files) != 1:
            # Send notification about multiple video files found
            if self.notification_service:
                self.notification_service.send_notification_to_all_providers(
                    title="Manual Import Required",
                    message=f"Multiple video files found for movie {movie.name}. Please import manually.",
                )
            log.error(
                f"Found {len(video_files)} video files for movie {movie.name}, expected 1. Skipping auto import."
            )
            return

        log.debug(
            f"Importing these {len(video_files)} video files and {len(subtitle_files)} subtitle files"
        )

        movie_files: list[MovieFile] = self.torrent_service.get_movie_files_of_torrent(
            torrent=torrent
        )
        log.info(
            f"Found {len(movie_files)} movie files associated with torrent {torrent.title}"
        )

        success = [
            self.import_movie(
                movie, video_files, subtitle_files, movie_file.file_path_suffix
            )
            for movie_file in movie_files
        ]

        if success and all(success):
            from media_manager.movies.models import Movie as LibraryModel
            self.movie_repository.db.get(LibraryModel,movie.id).request_only=False
            torrent.imported = True
            self.torrent_service.torrent_repository.save_torrent(torrent=torrent)

            if self.notification_service:
                self.notification_service.send_notification_to_all_providers(
                    title="Movie Downloaded",
                    message=f"Movie {movie.name} has been successfully downloaded and imported.",
                )
        else:
            log.error(
                f"Failed to import files for torrent {torrent.title}. Check logs for details."
            )

            if self.notification_service:
                self.notification_service.send_notification_to_all_providers(
                    title="Import Failed",
                    message=f"Failed to import files for movie {movie.name}. Please check logs.",
                )

        log.info(f"Finished importing files for torrent {torrent.title}")

    def get_import_candidates(
        self, movie: Path, metadata_provider: AbstractMetadataProvider
    ) -> MediaImportSuggestion:
        search_result = self.search_for_movie(
            query=remove_special_chars_and_parentheses(movie.name),
            metadata_provider=metadata_provider,
        )
        import_candidates = MediaImportSuggestion(
            directory=movie,
            candidates=search_result,
        )
        log.debug(
            f"Found {len(search_result)} candidates for {movie.name} in {movie.parent}"
        )
        return import_candidates

    def catalogue_existing_movie(self, movie: Movie, source_directory: Path) -> bool:
        files = video_files(source_directory)
        if not files:
            return False
        self.movie_repository.add_movie_file(MovieFile(
            movie_id=movie.id, file_path_suffix=catalogue_suffix(source_directory),
            torrent_id=None, quality=Quality.unknown, source_files=files,
        ))
        return True

    def import_existing_movie(self, movie: Movie, source_directory: Path) -> bool:
        new_source_path = source_directory.parent / ("." + source_directory.name)
        try:
            source_directory.rename(new_source_path)
        except Exception as e:
            log.exception(f"Failed to rename {source_directory} to {new_source_path}")
            raise RenameError from e

        video_files, subtitle_files, _all_files = get_files_for_import(
            directory=new_source_path
        )

        success = self.import_movie(
            movie=movie,
            video_files=video_files,
            subtitle_files=subtitle_files,
            file_path_suffix="IMPORTED",
        )
        if success:
            self.movie_repository.add_movie_file(
                MovieFile(
                    movie_id=movie.id,
                    file_path_suffix="IMPORTED",
                    torrent_id=None,
                    quality=Quality.unknown,
                )
            )

        return success

    def update_movie_metadata(
        self, db_movie: Movie, metadata_provider: AbstractMetadataProvider
    ) -> Movie | None:
        """
        Updates the metadata of a movie.

        :param metadata_provider: The metadata provider object to fetch fresh data from.
        :param db_movie: The Movie to update
        :return: The updated Movie object, or None if the movie is not found or an error occurs.
        """
        log.debug(f"Found movie: {db_movie.name} for metadata update.")

        # Use stored original_language preference for metadata fetching
        fresh_movie_data = metadata_provider.get_movie_metadata(
            movie_id=db_movie.external_id, language=db_movie.original_language
        )
        if not fresh_movie_data:
            log.warning(
                f"Could not fetch fresh metadata for movie: {db_movie.name} (ID: {db_movie.external_id})"
            )
            return None
        log.debug(f"Fetched fresh metadata for movie: {fresh_movie_data.name}")

        self.movie_repository.update_movie_attributes(
            movie_id=db_movie.id,
            name=fresh_movie_data.name,
            overview=fresh_movie_data.overview,
            year=fresh_movie_data.year,
            imdb_id=fresh_movie_data.imdb_id,
        )

        updated_movie = self.movie_repository.get_movie_by_id(movie_id=db_movie.id)

        log.info(f"Successfully updated metadata for movie ID: {db_movie.id}")
        metadata_provider.download_movie_poster_image(movie=updated_movie)
        return updated_movie

    def get_importable_movies(
        self, metadata_provider: AbstractMetadataProvider, discover_only: bool = False
    ) -> list[MediaImportSuggestion]:
        movie_root_path = MediaManagerConfig().misc.movie_directory
        importable_movies: list[MediaImportSuggestion] = []
        candidate_dirs = get_importable_media_directories(movie_root_path)

        catalogued = {}
        root = movie_root_path.resolve()
        for stored in self.movie_repository.catalogued_source_files():
            path = Path(stored)
            try:parts=path.relative_to(root).parts
            except ValueError:continue
            if len(parts)>1:catalogued.setdefault(parts[0],[]).append(path)
        for movie_dir in candidate_dirs:
            if any(p.is_file() for p in catalogued.get(movie_dir.name,[])):
                continue
            metadata, external_id = extract_external_id_from_string(movie_dir.name)
            if metadata is not None and external_id is not None:
                try:
                    known = self.movie_repository.get_movie_by_external_id(
                        external_id=external_id, metadata_provider=metadata
                    )
                    log.debug(
                        f"Movie {movie_dir.name} already exists in the database, skipping."
                    )
                    if self.is_movie_downloaded(known):
                        continue
                except NotFoundError:
                    log.debug(
                        f"Movie {movie_dir.name} not found in database, checking for import candidates."
                    )

            if discover_only:
                importable_movies.append(MediaImportSuggestion(directory=movie_dir, candidates=[]))
                continue

            try:
                import_candidates = self.get_import_candidates(
                    movie=movie_dir, metadata_provider=metadata_provider
                )
            except Exception:
                log.warning("Metadata lookup failed for library scan directory %s", movie_dir)
                import_candidates = MediaImportSuggestion(directory=movie_dir, candidates=[])
            importable_movies.append(import_candidates)

        log.debug(f"Found {len(importable_movies)} importable movies.")
        return importable_movies


def auto_download_all_approved_movie_requests() -> None:
    """
    Auto download all approved movie requests.
    This is a standalone function as it creates its own DB session.
    """
    db: Session = SessionLocal() if SessionLocal else next(get_session())
    movie_repository = MovieRepository(db=db)
    torrent_service = TorrentService(torrent_repository=TorrentRepository(db=db))
    indexer_service = IndexerService(indexer_repository=IndexerRepository(db=db))
    notification_service = NotificationService(
        notification_repository=NotificationRepository(db=db)
    )
    movie_service = MovieService(
        movie_repository=movie_repository,
        torrent_service=torrent_service,
        indexer_service=indexer_service,
        notification_service=notification_service,
    )

    log.info("Auto downloading all approved movie requests")
    movie_requests = movie_repository.get_movie_requests()
    log.info(f"Found {len(movie_requests)} movie requests to process")
    count = 0

    for movie_request in movie_requests:
        if movie_request.authorized:
            movie = movie_repository.get_movie_by_id(movie_id=movie_request.movie_id)
            if movie_service.download_approved_movie_request(
                movie_request=movie_request, movie=movie
            ):
                count += 1
            else:
                log.info(
                    f"Could not download movie request {movie_request.id} for movie {movie.name}"
                )

    log.info(f"Auto downloaded {count} approved movie requests")
    db.commit()
    db.close()


def import_all_movie_torrents() -> None:
    with next(get_session()) as db:
        movie_repository = MovieRepository(db=db)
        torrent_service = TorrentService(torrent_repository=TorrentRepository(db=db))
        indexer_service = IndexerService(indexer_repository=IndexerRepository(db=db))
        notification_service = NotificationService(
            notification_repository=NotificationRepository(db=db)
        )
        movie_service = MovieService(
            movie_repository=movie_repository,
            torrent_service=torrent_service,
            indexer_service=indexer_service,
            notification_service=notification_service,
        )
        log.info("Importing all torrents")
        torrents = torrent_service.get_all_torrents()
        log.info("Found %d torrents to import", len(torrents))
        for t in torrents:
            try:
                if not t.imported and t.status == TorrentStatus.finished:
                    movie = torrent_service.get_movie_of_torrent(torrent=t)
                    if movie is None:
                        log.warning(
                            f"torrent {t.title} is not a movie torrent, skipping import."
                        )
                        continue
                    movie_service.import_torrent_files(torrent=t, movie=movie)
            except RuntimeError:
                log.exception(f"Failed to import torrent {t.title}")
        log.info("Finished importing all torrents")
        db.commit()


def update_all_movies_metadata() -> None:
    """
    Updates the metadata of all movies.
    """
    with next(get_session()) as db:
        movie_repository = MovieRepository(db=db)
        movie_service = MovieService(
            movie_repository=movie_repository,
            torrent_service=TorrentService(torrent_repository=TorrentRepository(db=db)),
            indexer_service=IndexerService(indexer_repository=IndexerRepository(db=db)),
            notification_service=NotificationService(
                notification_repository=NotificationRepository(db=db)
            ),
        )

        log.info("Updating metadata for all movies")

        movies = movie_repository.get_movies()

        log.info(f"Found {len(movies)} movies to update")

        for movie in movies:
            try:
                if movie.metadata_provider == "tmdb":
                    metadata_provider = TmdbMetadataProvider()
                elif movie.metadata_provider == "tvdb":
                    metadata_provider = TvdbMetadataProvider()
                else:
                    log.error(
                        f"Unsupported metadata provider {movie.metadata_provider} for movie {movie.name}, skipping update."
                    )
                    continue
            except InvalidConfigError:
                log.exception(
                    f"Error initializing metadata provider {movie.metadata_provider} for movie {movie.name}",
                )
                continue
            movie_service.update_movie_metadata(
                db_movie=movie, metadata_provider=metadata_provider
            )
        db.commit()
