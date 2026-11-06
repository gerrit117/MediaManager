# Existing media libraries

Admins manage scans under **Settings → Library**. The dashboard and movie/series pages link directly to this area.

**Start library scan and import** runs a background job that registers existing media in the database and reports progress, errors and folders needing review. It uses explicit IDs in movie/show NFO files or optional read-only metadata from existing Radarr/Sonarr installations. Source media roots map the source application's top-level folders to MediaManager's configured movie/TV roots. Conflicting or missing identities are left for manual matching; the scanner does not guess from a title.

Choose an import mode:

- **Catalogue only** (default) records existing paths without renaming, moving, unpacking or changing media permissions. It does not create download requests or enable series monitoring. Poster images can be copied into MediaManager's image cache.
- **Reorganize into library folders** requires explicit confirmation and uses the existing importer, including source-folder renaming, archive extraction and copied/hardlinked output. Back up existing libraries before reorganizing.

Optional Radarr/Sonarr connections, API keys, source media roots, automatic scans and the interval are editable in the Library area. API keys are persisted privately on the server and are never returned to the browser. These settings apply live. Configured application media paths are shown in the Library area; change container/library paths in System & Downloads and restart when prompted.

Automatic schedules are checked hourly and always use catalogue-only mode. Repeated scans refresh recorded files without duplicating titles. Stored file-to-title mappings continue to identify previously catalogued media after optional source services are removed. Existing IDs, libraries and monitoring preferences are preserved. A persistent status file and process lock prevent concurrent scans; an interrupted job can be started again safely.

Unresolved folders have **Match manually** links to the existing metadata-search/import dialog. Movie/show lists initially render a limited number of cards and provide **Show more entries**. Dashboard counts refresh after catalogue changes.

## Series monitoring

Enable **Monitor new episodes and seasons** on a series to follow aired episodes from activation onward. Importing an existing library does not enable it automatically. See [episode monitoring and release rules](episode-monitoring.md).
