# Usenet edition

Based on upstream v1.12.3. Independent fork under the original AGPL-3.0 license; upstream attribution and history are retained. The release runtime is pinned by digest. There is no database migration in this version.

## Preserved functionality

- Movie and season requests, approval and existing request scheduling.
- TMDB/TVDB metadata, existing library paths and IDs.
- qBittorrent and Transmission clients, alongside SABnzbd.
- Existing torrent API URLs and database models. UI wording no longer assumes every download is a torrent.

Do not replace this branch wholesale with upstream master: PR 455 removed the request feature, and PRs 454/461/541 change database/scheduler/backend architecture.

## NZB changes

- Direct standards-based Newznab connection in Settings, initially used with Treasure Maps.
- Discover available indexer categories; select movie and TV categories separately.
- API keys stored only in private persistent backend settings, not returned to the browser.
- SABnzbd category selection, per-job status/history lookup, normalized completed-path mapping and repair/unpack/delete postprocessing.
- Download cards with progress and separate actions. NZB/torrent labels are distinct. Progress supports SABnzbd, qBittorrent and Transmission.
- Resume only paused jobs; retry only failed SABnzbd jobs. Running jobs cannot be restarted by the action shown in the UI.
- Existing requests are preserved; this fork is not yet a feature-complete replacement for Sonarr/Radarr language profiles and automatic upgrades.

## Reviewed upstream changes

| Upstream reference | Treatment |
| --- | --- |
| PR 450 | Backported expanded 2160p/UHD/FullHD quality detection. |
| PR 499 (closed, not merged upstream) | Adapted scoring for custom movie/season searches; unrelated example DB-host change omitted. |
| PR 473 | Adapted whole-keyword scoring, including punctuation such as DD+; unrelated redirect-return deletion omitted. |
| PR 489 | Reimplemented Enter submission in this release's shared search component using Svelte 5 syntax. |
| PR 519 (draft) | Adapted manual import search; added network-error recovery, state reset and responsive controls. |
| PR 558 | Backported configurable qBittorrent category and support for old/new add responses. |
| PR 569 | Writable UV cache location in the original application Dockerfile; the edition image also supports a persistent cache. Relay image is not changed. |
| Issue 573 | ID-based Newznab queries no longer combine an ID with free-text q; explicit custom searches remain text searches. |
| Issue 453 | Validate filename suffixes before submission and import; reject path separators, traversal and control characters. |
| PRs 272/365/516/564 | Not merged wholesale: stale WIP, provider refactor, unused alternative client, or async/schema dependencies. |
| PRs 454/455/461/541 | Excluded from this stable edition to retain requests and avoid untested migrations. |

References use https://github.com/maxdorninger/MediaManager/pull/NUMBER and /issues/NUMBER. Closed or draft proposals are credited as sources, not represented as approved upstream fixes. No blanket merge of dependency-update PRs is performed.

## Build and configure

Build the tested amd64 edition:

```sh
docker build -f Dockerfile.usenet -t mediamanager:1.12.3-usenet.1 .
```

Run all backend checks and build the UI:

```sh
docker build -f Dockerfile.usenet --target checks .
```

Keep the existing database and persistent configuration mounts. Unraid may run the image as UID 99/GID 100, with writable configuration, cache, image, media and download mounts owned by those IDs. Never commit an actual server configuration or API key.

Example additional backend configuration:

```toml
[torrents.sabnzbd]
enabled = true
host = "http://sabnzbd"
port = 8080
base_path = "/api"
api_key = "REPLACE_LOCALLY"
category = "mediamanager"
remote_download_directory = "/downloads/mediamanager"
```

The remote directory must map to the same completed-download location as `misc.torrent_directory` inside MediaManager. If torrent clients and SABnzbd use separate completed directories, configure their mounts accordingly; do not point an unrelated client at the SABnzbd category directory. A general download-client settings UI is planned separately.

Original upstream Docker/documentation publication jobs are restricted to the upstream repository. This fork runs its own regression-check workflow and does not attempt to publish to upstream registries or pages. It does not automatically merge upstream changes. Review/backport new fixes individually.

## Verification limits

Unit/API contract tests cover protocol routing, old/new qBittorrent responses, progress, status, scoring, quality and suffix validation. Real-client integration results are recorded separately with the release; a mocked test alone is not described as a real torrent transfer. Tests use self-created payloads and no third-party media.

OIDC remains disabled by default; the upstream email-association concern in issue 575 is not solved by these changes. Review it before enabling OIDC. German metadata and German audio preferences are separate; no claim is made that indexer categories guarantee an audio language.

### Verified release checks

- 92 backend tests passed (including protocol routing and compatibility cases).
- Isolated real qBittorrent and Transmission 4.1.4: add an own magnet, pause, resume, query progress and delete succeeded. The test network had no Internet access; this checks client control, not a complete peer transfer.
- The frontend dependency lock was repaired so a clean `npm ci` build is reproducible; package declarations were not changed.
