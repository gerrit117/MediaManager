# Library details and movie collections

## Series identities

TMDB and TheTVDB assign different IDs to the same series. MediaManager keeps provider aliases and verified IMDb links so that searching with another provider opens an existing series rather than adding an empty duplicate. Titles alone are not enough to merge records. The metadata editor changes descriptive metadata and provider IDs while preserving internal file/request identities. Conflicting identities require administrator review.

## Seasons and episodes

Expand a season to see each episode, its air date and whether a file is present. Future episodes are marked Upcoming rather than Missing; absent air dates are shown explicitly. Empty seasons are hidden. Season 0 contains optional specials and appears separately after regular seasons when metadata actually contains episodes.

Administrators can search a season or an individual episode. Users can request either through the same approval and monthly-quota policies as movie requests. Each individual episode request consumes one request. Approved episode requests are checked every 15 minutes. Submission claims prevent automatic retries when a download manager response is uncertain. Existing download clients and global release rules apply to both NZB and torrent releases.

## Import destination

The library selector chooses the target directory for future imports. It does not rename existing files, move catalogued media, or identify a title. Use metadata editing to correct a title or provider ID. Library scans offer separate catalogue-in-place and file-reorganization modes.

## Movie collections

Open **Movies → Movie collections**. Collection membership is cached in PostgreSQL and matched to MediaManager's own catalogue, including actual recorded file paths. A missing member opens its normal movie details for searching (Admin) or requesting (User); opening the page does not submit a download.

An administrator can refresh collection metadata from a configured Radarr connection or directly from TMDB. Direct TMDB discovery and full collection refresh require a personal TMDB **v3 API key**. Set it in **Settings → System & Downloads → Metadata**, or pass `MEDIAMANAGER_METADATA__TMDB__API_KEY` when creating the Docker container. A nonempty environment variable takes precedence over private web settings. Empty variables do not override stored keys. Recreate a container after changing its environment; keys saved through web settings apply immediately.

A refresh only changes cached metadata, never media files or Radarr configuration. Future members are shown as Upcoming. Refresh progress and connection errors appear on the collection page. Existing relay-based metadata and download/request workflows do not require a personal key.

See [TMDB's documented collection endpoint](https://developer.themoviedb.org/reference/collection-details). This product uses the TMDB API but is not endorsed or certified by TMDB.
