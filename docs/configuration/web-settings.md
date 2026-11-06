# Setup, settings and release filters

The Usenet edition retains the v1.12.3 request system. It has Admin and User roles, per-user monthly quotas and an automatic-approval checkbox; see request-policies.md. Normal users can search and request media; downloading, imports, approval and server settings require a superuser. Request creation may add metadata entries to the library; this is not a strictly isolated request-only portal. Request lists are visible to signed-in users. Administrators' requests are approved automatically. Monthly limits and automatic approval are configurable per user. The ownership check for movie edits and season-request editing were corrected in this release; approval/requester/season are preserved when editing quality.

## Quick filters

Movie and season release searches offer resolution, video source, audio and protocol buttons. Within a group selections mean OR; across groups AND. Reset restores all fetched releases. These are filename-tag heuristics, not a scan of downloaded streams, and do not change scheduled searches, scoring or download policies. They cannot enforce German audio automatically. Missing source/audio tags remain unknown.

## Existing installations

Administrators can use Settings → System & Downloads for library/container paths, metadata language, database connection, SABnzbd, qBittorrent, Transmission, sessions and OIDC. Settings → Indexer services has separate Integrated, Prowlarr and Jackett tabs, each with its configuration and categories. Stored secrets are never returned by this API. Empty secret fields retain the existing secret. Environment-controlled fields are read-only. Connection and metadata changes apply live to new operations. Database, path and sign-in changes are staged until the next application restart.

The existing config.toml is retained. Connection and metadata changes are written privately to settings.json and used by new operations immediately. Changes requiring a restart are stored in settings.pending.json beside it, then activated at startup. A previous settings.json is backed up as settings.json.bak. File modes are 0600. Environment values override settings.json, which overrides config.toml. Removing/renaming settings.json and settings.pending.json restores the original TOML configuration on restart. UI settings are intentionally curated; notifications, scoring-rule editors, additional library definitions and download-manager-internal extraction/Usenet-server rules are not yet exposed. Do not enable OIDC until the upstream account-association concern has been resolved.

## Fresh installation

The edition entrypoint detects a missing config.toml before the original startup script or database migrations run and serves an initial setup wizard on the normal HTTP port. It creates a private setup-code file in the writable configuration mount. Read that file locally or supply MEDIAMANAGER_SETUP_CODE before the first start. This prevents unauthenticated visitors from claiming the installation. The code is not logged. With the standard image alone, PostgreSQL must already exist and be reachable; the wizard checks the connection and refuses to provision a new admin over an existing user database. Mounted library paths must be writable.

The wizard generates a private config.toml with a random signing secret, the entered database/path settings and German metadata preference. A one-use private initial-admin.json supplies the chosen administrator password; it is removed after successful account creation, together with setup-code. Passwords are not printed to logs. The application then runs the existing migrations and starts normally without manual container restart. Existing installations skip this process and keep their accounts and configuration.

Use UID 99/GID 100 on Unraid with matching writable mounts. The wizard does not chown existing media recursively. A PostgreSQL failure after initial setup still needs correction of the database service/permissions; it never resets the database automatically.

## Image updates

The fork's master workflow builds the frontend and runs backend/filter tests before publishing ghcr.io/gerrit117/mediamanager:latest plus an immutable sha-COMMIT tag. PRs only run checks. The registry package must be Public for anonymous Unraid pulls; GitHub initially creates new packages Private. Unraid's normal update action pulls latest and recreates the container while retaining mounts. This does not install upstream master changes automatically and does not enable unattended restarts.

## Download engines and database architecture

A unified UI can manage existing SABnzbd and qBittorrent/Transmission via their documented APIs. This is preferable to writing NNTP, PAR repair, extraction, BitTorrent peer management and resume logic again. A bundled edition could run these daemons with supervision, separate users/directories, persistent queues and explicit extraction/seeding policies, but larger images, shared restarts and more difficult security/engine updates follow. Local daemons can use loopback APIs; a CLI is useful for process launch, not for parsing textual status when a structured API exists.

PostgreSQL can also share a container technically, but needs supervised startup, graceful shutdown, major-version migrations, physical backups and a persistent data directory. Keep the existing separate PostgreSQL service. A compose stack or an Unraid folder gives a single application group while retaining independent upgrades and failure boundaries. No download engine or production database was moved into this image.

The optional [managed stack](managed-stack.md) provisions a separate database service and application account automatically. The new [request policies](request-policies.md) include monthly limits, automatic approval and interface language selection.
