# MediaManager

An independent fork of [MediaManager by Maximilian Dorninger and contributors](https://github.com/maxdorninger/MediaManager), extending the v1.12.3 foundation with direct indexer access, guided configuration and a clearer download interface. **Both Usenet/NZB and torrents are supported.**

This is a community fork, not an official upstream release. The original project's attribution, license and Git history are retained.

Account setup and the request-first workflow are documented in [Accounts and requests](docs/accounts-and-requests.md): single-use invitations, email confirmation/recovery through SMTP, shared movie/season quotas and per-user progress.

## What differs here

- Separate movie/series discovery with TMDB trends, popular/top-rated/recent lists, and country-specific streaming provider, studio and genre filters.
- Built-in movie and season requests remain available.
- Manual release replacement with recovery archives and inherited upgrade protection for movies, series, seasons and episodes.
- Per-account HTML email and PWA push notifications for request approvals, rejections and Emby-confirmed availability.
- Read-only Emby library matching using provider IDs and episode identities.
- Admins can create user accounts directly in web settings.
- Background library imports use trusted NFO IDs or optional Radarr/Sonarr metadata, with progress, manual review, repeatable scans and an explicit choice of catalogue-in-place or file reorganization.
- Episode monitoring follows weekly releases within existing seasons, with persistent submission deduplication and targeted imports.
- Shared language/resolution preferences and release exclusions apply to all indexer providers and manual/automatic downloads.
- Exactly two roles: Admin and User. Administrators can set each user's monthly request quota and automatic approval.
- Persistent quota accounting covers movies, seasons and individual episode requests together and cannot be bypassed by deleting requests or making concurrent submissions.
- Direct Newznab connection and indexer-advertised category discovery, alongside Prowlarr and Jackett.
- SABnzbd, qBittorrent and Transmission integration, with protocol-aware download labels and progress.
- Quick release filters for resolution, video source, audio tags and download type.
- Separate settings tabs, including Integrated/Prowlarr/Jackett indexer tabs, and English/German interface selection.
- Web configuration with private credential storage. Connection and metadata changes apply live; database, path and sign-in changes are staged for restart.
- First-run wizard and an optional managed Docker stack that provisions a separate PostgreSQL service, application database and limited application role automatically.
- Selected upstream fixes are reviewed and backported while retaining the request workflow.

## Install

The standard image uses existing external services:

```sh
docker pull ghcr.io/gerrit117/mediamanager:latest
```

For a new managed stack, use [the installation guide](docs/configuration/managed-stack.md). PostgreSQL remains a separate container. Existing download managers can be reused; optional Compose profiles provide separate SABnzbd and qBittorrent services.

On Unraid, use UID 99/GID 100 with writable persistent mounts. Keep existing configuration and database backups before upgrading. New database migrations are included in the image; do not replace a populated PostgreSQL data directory to upgrade it.

## TMDB API key

Set `MEDIAMANAGER_METADATA__TMDB__API_KEY` to your own TMDB v3 API key for direct TMDB access, including discovery, provider/studio filters, full movie-collection membership and missing collection entries. Obtain a key in your [TMDB account settings](https://www.themoviedb.org/settings/api). Existing relay-based movie and series metadata, requests and downloads do not require a personal TMDB key.

You can either supply the variable when creating the Docker container, or enter the key in the administrator web settings. An environment variable takes precedence and makes the corresponding web setting read-only; recreate the container after changing its environment. Keys entered through web settings are stored privately in the persistent configuration directory and are not returned to the browser. Keep keys out of committed Compose files and shared container diagnostics.

```sh
# Export the key in your shell or deployment secret environment first.
docker run --env MEDIAMANAGER_METADATA__TMDB__API_KEY \
  --volume /your/config:/app/config \
  --publish 8095:8000 ghcr.io/gerrit117/mediamanager:latest
```

For the managed Compose stack, export the same variable before starting it. On Unraid, add a Variable with this exact key and enable masking, or use [the container template](ops/unraid-mediamanager.xml). Leaving the variable unset keeps the web settings option available.

## Documentation

- [Release replacement, notifications and Emby](docs/media-replacements-and-notifications.md)

- [Movie and series discovery](docs/discovery.md)

- [Requests, policies and language selection](docs/configuration/request-policies.md)
- [Episode monitoring and release rules](docs/episode-monitoring.md)
- [Existing libraries and series monitoring](docs/library-import.md)
- [Series identities, episode actions and movie collections](docs/library-details.md)
- [Setup and web settings](docs/configuration/web-settings.md)
- [Managed stack](docs/configuration/managed-stack.md)
- [Upstream review and backports](docs/upstream-tracking.md)
- [Earlier changes and known limitations](docs/usenet-edition.md)

Build from source with `docker build -f Dockerfile.usenet -t mediamanager .`.

## Thanks

Thanks to **Maximilian Dorninger (`maxdorninger`) and all original MediaManager contributors** for creating and maintaining the project this fork is based on.

The integrations rely on the work of [SABnzbd](https://github.com/sabnzbd/sabnzbd), [qBittorrent](https://github.com/qbittorrent/qBittorrent), [Transmission](https://github.com/transmission/transmission), [Prowlarr](https://github.com/Prowlarr/Prowlarr), [Jackett](https://github.com/Jackett/Jackett), the Newznab ecosystem and [PostgreSQL](https://www.postgresql.org/). Thank you to their maintainers and contributors. These are external integrations/optional services; their engines are not bundled into the standard MediaManager image.

Media metadata comes from TMDB and TheTVDB via the configured providers. Original upstream documentation remains available [here](https://maxdorninger.github.io/MediaManager/).

## License

AGPL-3.0, as inherited from the original project. See [the license](LICENSE).
