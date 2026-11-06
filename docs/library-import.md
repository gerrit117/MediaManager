# Existing media libraries

Admins can use **Scan existing library** on Movies and TV to find unrecognised folders in the configured movie/TV root. Scanning is manual and read-only. It lists directories first; metadata matching is loaded when opening a directory so large libraries do not need a separate external search for every folder before anything is shown. Match each directory to a metadata result; manual TMDB/TVDB search is available when the suggested title is incorrect or a lookup fails.

Choose an import mode before selecting a result:

- **Catalogue only** (default) registers existing video file paths without renaming, moving or unpacking anything. Archives alone are not playable media and are not extracted. Series filenames must identify episodes, for example `Show.S01E01.mkv` or `Show.1x01.mp4`. Partial seasons are recorded but are not marked complete. A subsequent import refreshes the recorded file list; missing files no longer count as available.
- **Reorganize into library folders** uses the existing importer after a separate confirmation. It renames the source folder with a leading dot, extracts archives where applicable, and copies or links media into MediaManager's configured naming structure. The original importer's disk-space and backup requirements still apply.

Catalogued files retain their original paths. Changing container mount paths later requires importing those directories again. The scanner currently discovers directories under the configured main roots; loose files directly in a root should first be put into a media directory. It does not start downloads or change the request list.

## Series monitoring

The series details page offers **Monitor new episodes and seasons**. It tracks aired episodes from activation onward, including weekly releases inside an existing season, and retains claims across restarts. See [episode monitoring and release rules](episode-monitoring.md) for scheduling, exclusions and upgrade behavior.
