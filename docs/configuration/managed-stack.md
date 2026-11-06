# Managed installation

The managed stack is optional. Existing installations keep their database and download services; do not run this installer over an existing unmanaged directory.

Requirements: Docker, Docker Compose (plugin or standalone), Python 3, existing writable movie/TV/download directories, and permissions to create the selected persistent state directory. No Docker socket is mounted in the application.

Example for a **new** Unraid installation (choose an unused port if another installation is running):

```sh
python3 ops/setup-stack.py \
  --directory /mnt/user/appdata/mediamanager-new \
  --movies /mnt/user/Medien/Filme \
  --tv /mnt/user/Medien/Serien \
  --downloads /mnt/user/Downloads/finished \
  --port 8095
```

Add `--with-nzb` and/or `--with-torrent` to start optional, separate SABnzbd/qBittorrent services. Their UIs default to ports 8096/8097 (override MM_SAB_PORT/MM_QBIT_PORT before running if needed). Configure existing or optional clients from the guided settings page. Their daemon hostnames on the managed network are sabnzbd and qbittorrent, each port 8080. SABnzbd still needs your NNTP provider and download/extraction configuration. Engines are never enabled for MediaManager just because their container exists.

The installer creates persistent random admin/application database passwords once, stored as 0600 files. The separate official PostgreSQL 17 service initializes an empty data directory, creates the mediamanager database and a dedicated login that is not a superuser and cannot create roles or databases. The app receives only its own password. Secrets are mounted as files; they are not written into the Compose environment file or printed to logs.

Open the selected port and read the private setup-code inside the new config directory. The wizard checks the preconfigured DB connection and writable library mounts, generates a signing secret and creates the chosen administrator account. One-use bootstrap credentials are removed after successful creation. After login, the guided settings page provides optional indexer/downloader configuration; you may skip and configure later.

Subsequent runs preserve credentials and data. If PostgreSQL data exists but its password files are missing, installation stops rather than silently generating incompatible passwords. Back up the state and logical database dumps. PostgreSQL major versions are fixed; major upgrades need deliberate migration. No existing server's database or download client is adopted, reset or removed.

Use the same state and project name to update. Apply Compose pulls/recreation on the user side; the installer does not enable unattended updates. `--prepare-only` writes configuration without launching services. `--compose-binary` can point at a standalone Compose executable.
