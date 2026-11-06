"""Persistent, staged administrator settings. No database/import side effects."""
import fcntl
import json
import os
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any


def config_file() -> Path:
    return Path(os.getenv('CONFIG_FILE') or Path(os.getenv('CONFIG_DIR', '/app/config')) / 'config.toml')


def settings_file(pending=False) -> Path:
    return config_file().parent / ('settings.pending.json' if pending else 'settings.json')


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def merge(base: dict, changes: dict) -> dict:
    result = dict(base)
    for key, value in changes.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def nested(values: dict) -> dict:
    result: dict = {}
    for key, value in values.items():
        cursor = result
        parts = key.split('.')
        for part in parts[:-1]: cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return result


def lookup(data: dict, key: str):
    value = data
    for part in key.split('.'): value = value.get(part, {}) if isinstance(value, dict) else None
    return value


# Fields exposed deliberately: signing secrets and internal flags are never returned.
FIELDS: list[tuple[str, str, str]] = [
 ('indexers.release_policy.enabled','Enforce release rules for every download','bool'),
 ('indexers.release_policy.languages','Language priority (de, en)','list'),
 ('indexers.release_policy.resolutions','Resolution priority (2160p, 1080p, 720p, 480p)','list'),
 ('indexers.release_policy.excluded_tags','Excluded release tags','list'),
 ('indexers.release_policy.allow_unknown_language','Allow releases with unidentified language','bool'),
 ('misc.movie_directory','Filme','path'),('misc.tv_directory','Serien','path'),('misc.torrent_directory','Abgeschlossene Downloads (Containerpfad)','path'),('misc.image_directory','Vorschaubilder','path'),('misc.frontend_url','WebUI-Adresse','text'),
 ('metadata.tmdb.default_language','Metadaten: Standardsprache','text'),('metadata.tmdb.primary_languages','Metadaten: bevorzugte Sprachen (z. B. de,en)','list'),
 ('database.host','Datenbank: Host','text'),('database.port','Datenbank: Port','number'),('database.dbname','Datenbank: Name','text'),('database.user','Datenbank: Benutzer','text'),('database.password','Datenbank: Passwort','secret'),
 ('torrents.sabnzbd.enabled','SABnzbd verwenden (NZB)','bool'),('torrents.sabnzbd.host','SABnzbd: Adresse mit http(s)://','text'),('torrents.sabnzbd.port','SABnzbd: Port','number'),('torrents.sabnzbd.api_key','SABnzbd: API-Key','secret'),('torrents.sabnzbd.base_path','SABnzbd: API-Pfad','text'),('torrents.sabnzbd.category','SABnzbd: Kategorie','text'),('torrents.sabnzbd.remote_download_directory','SABnzbd: fertiger Pfad im Downloadmanager','text'),
 ('torrents.qbittorrent.enabled','qBittorrent verwenden (Torrent)','bool'),('torrents.qbittorrent.host','qBittorrent: Adresse','text'),('torrents.qbittorrent.port','qBittorrent: Port','number'),('torrents.qbittorrent.username','qBittorrent: Benutzer','text'),('torrents.qbittorrent.password','qBittorrent: Passwort','secret'),('torrents.qbittorrent.category_name','qBittorrent: Kategorie','text'),('torrents.qbittorrent.category_save_path','qBittorrent: Kategoriepfad','text'),
 ('torrents.transmission.enabled','Transmission verwenden (Torrent)','bool'),('torrents.transmission.host','Transmission: Host','text'),('torrents.transmission.port','Transmission: Port','number'),('torrents.transmission.username','Transmission: Benutzer','text'),('torrents.transmission.password','Transmission: Passwort','secret'),('torrents.transmission.https_enabled','Transmission: HTTPS','bool'),('torrents.transmission.path','Transmission: RPC-Pfad','text'),
 ('indexers.prowlarr.enabled','Prowlarr verwenden (NZB/Torrent)','bool'),('indexers.prowlarr.url','Prowlarr: Adresse','text'),('indexers.prowlarr.api_key','Prowlarr: API-Key','secret'),('indexers.jackett.enabled','Jackett verwenden (Torrent)','bool'),('indexers.jackett.url','Jackett: Adresse','text'),('indexers.jackett.api_key','Jackett: API-Key','secret'),('indexers.jackett.indexers','Jackett: Indexer (kommagetrennt)','list'),
 ('auth.session_lifetime','Anmeldedauer (Sekunden)','number'),('auth.openid_connect.enabled','OIDC verwenden','bool'),('auth.openid_connect.name','OIDC: Anzeigename','text'),('auth.openid_connect.configuration_endpoint','OIDC: Discovery-Adresse','text'),('auth.openid_connect.client_id','OIDC: Client-ID','text'),('auth.openid_connect.client_secret','OIDC: Client-Secret','secret'),
]


def staged_values() -> dict:
    from media_manager.config import MediaManagerConfig
    live = MediaManagerConfig().model_dump(mode='json')
    path = settings_file(True)
    return merge(live, json.loads(path.read_text())) if path.exists() else live


def fields_for_browser() -> list[dict]:
    data = staged_values()
    return [dict(key=key, label=label, kind=kind,
                 value=None if kind == 'secret' else lookup(data, key),
                 configured=bool(lookup(data,key)) if kind == 'secret' else False,
                 environment=bool(os.getenv('MEDIAMANAGER_'+key.upper().replace('.', '__')) is not None)) for key,label,kind in FIELDS]


def stage_settings(values: dict, apply_live: bool = False) -> dict:
    from media_manager.config import MediaManagerConfig
    kinds = {key: kind for key, _, kind in FIELDS}
    cleaned = {}
    for key,value in values.items():
        if key not in kinds: raise ValueError('Unbekannte Einstellung')
        if os.getenv('MEDIAMANAGER_'+key.upper().replace('.', '__')) is not None:
            raise ValueError('Eine Umgebungsvariable überschreibt diese Einstellung')
        kind = kinds[key]
        if kind == 'secret' and value in ('',None): continue  # Keep existing credentials.
        if kind == 'bool' and not isinstance(value,bool): raise ValueError('Ungültiger Schalter')
        if kind == 'number' and (isinstance(value,bool) or not isinstance(value,int) or value <= 0): raise ValueError('Ungültige Zahl')
        if kind == 'list' and (not isinstance(value,list) or not all(isinstance(x,str) for x in value)): raise ValueError('Ungültige Liste')
        if kind in ('text','secret','path') and not isinstance(value,str): raise ValueError('Ungültiger Text')
        if kind == 'path' and not Path(value).is_absolute(): raise ValueError('Containerpfade müssen absolut sein')
        cleaned[key] = value
    with open(config_file().parent / '.settings.lock','a') as lock:
        os.chmod(lock.name,0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = merge(staged_values(),nested(cleaned))
        if lookup(data,'torrents.qbittorrent.enabled') and lookup(data,'torrents.transmission.enabled'):
            raise ValueError('Bitte nur einen Torrent-Client aktivieren')
        # Validate without exposing Pydantic errors containing secret input.
        try: MediaManagerConfig(**data)
        except Exception: raise ValueError('Ungültige Konfiguration; Adressen, Ports und Werte prüfen') from None
        current = json.loads(settings_file().read_text()) if settings_file().exists() else {}
        pending = json.loads(settings_file(True).read_text()) if settings_file(True).exists() else {}
        proposed=merge(merge(current,pending),nested(cleaned))
        hot={key:value for key,value in cleaned.items() if key.startswith(('indexers.','torrents.','metadata.'))} if apply_live else {}
        if hot:
            active=merge(current,nested(hot))
            if settings_file().exists():
                shutil.copyfile(settings_file(),settings_file().with_suffix('.json.bak'))
                os.chmod(settings_file().with_suffix('.json.bak'),0o600)
            atomic_json(settings_file(),active)
        live=MediaManagerConfig().model_dump(mode='json')
        desired=merge(live,proposed)
        restart_required=any(lookup(live,key)!=lookup(desired,key) for key,_,_ in FIELDS)
        if not apply_live or restart_required:atomic_json(settings_file(True),proposed)
        else:settings_file(True).unlink(missing_ok=True)
        return {'restart_required':restart_required,'applied_live':bool(hot)}


def activate_settings() -> None:
    pending = settings_file(True)
    if not pending.exists(): return
    from media_manager.config import MediaManagerConfig
    data = json.loads(pending.read_text())
    MediaManagerConfig(**merge(MediaManagerConfig().model_dump(mode='json'),data))
    live = settings_file()
    if live.exists():
        shutil.copyfile(live,live.with_suffix('.json.bak'));os.chmod(live.with_suffix('.json.bak'),0o600)
    os.replace(pending,live)
