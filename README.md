# MediaManager

An independent fork of [MediaManager by Maximilian Dorninger and contributors](https://github.com/maxdorninger/MediaManager), extending the v1.12.3 foundation with direct indexer access, guided configuration and a clearer download interface. **Both Usenet/NZB and torrents are supported.**

This is a community fork, not an official upstream release. The original project's attribution, license and Git history are retained.

## What differs here

- Built-in movie and season requests remain available.
- Admins can create user accounts directly in web settings.
- Background library imports use trusted NFO IDs or optional Radarr/Sonarr metadata, with progress, manual review, repeatable scans and an explicit choice of catalogue-in-place or file reorganization.
- Episode monitoring follows weekly releases within existing seasons, with persistent submission deduplication and targeted imports.
- Shared language/resolution preferences and release exclusions apply to all indexer providers and manual/automatic downloads.
- Exactly two roles: Admin and User. Administrators can set each user's monthly request quota and automatic approval.
- Persistent quota accounting covers movies and seasons together and cannot be bypassed by deleting requests or making concurrent submissions.
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

## Documentation

- [Requests, policies and language selection](docs/configuration/request-policies.md)
- [Episode monitoring and release rules](docs/episode-monitoring.md)
- [Existing libraries and series monitoring](docs/library-import.md)
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
