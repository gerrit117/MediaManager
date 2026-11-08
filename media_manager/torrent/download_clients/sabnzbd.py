import logging
from pathlib import Path

import sabnzbd_api

from media_manager.config import MediaManagerConfig
from media_manager.exceptions import BadRequestError
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.torrent.download_clients.abstract_download_client import (
    AbstractDownloadClient,
)
from media_manager.torrent.schemas import Torrent, TorrentStatus

log = logging.getLogger(__name__)


class SabnzbdDownloadClient(AbstractDownloadClient):
    name = "sabnzbd"

    DOWNLOADING_STATE = (
        "Downloading",
        "Queued",
        "Paused",
        "Extracting",
        "Moving",
        "Running",
        "Fetching", "Propagating", "QuickCheck", "Verifying", "Repairing",
    )
    FINISHED_STATE = ("Completed",)
    ERROR_STATE = ("Failed",)
    UNKNOWN_STATE = ("Unknown",)

    def __init__(self) -> None:
        self.config = MediaManagerConfig().torrents.sabnzbd
        self.client = sabnzbd_api.SabnzbdClient(
            host=self.config.host,
            port=str(self.config.port),
            api_key=self.config.api_key,
        )
        self.client._base_url = f"{self.config.host.rstrip('/')}:{self.config.port}{self.config.base_path}"  # the library expects a /sabnzbd prefix for whatever reason
        try:
            # Test connection
            self.client.version()
        except Exception:
            log.exception("Failed to connect to SABnzbd")
            raise

    def download_torrent(self, indexer_result: IndexerQueryResult) -> Torrent:
        """
        Add a NZB/torrent to SABnzbd and return the torrent object.

        :param indexer_result: The indexer query result of the NZB file to download.
        :return: The torrent object with calculated hash and initial status.
        """
        try:
            # Add NZB to SABnzbd queue
            response = self.client.add_uri(
                url=str(indexer_result.download_url), nzbname=indexer_result.title,
                cat=self.config.category, pp=3,
            )
            if not response["status"]:
                raise RuntimeError(f"Failed to add NZB to SABnzbd: {response}")  # noqa: EM102, TRY003, TRY301

            # Generate a hash for the NZB (using title and download URL)
            nzo_id = response["nzo_ids"][0]

            # Create and return torrent object
            torrent = Torrent(
                status=TorrentStatus.unknown,
                title=indexer_result.title,
                quality=indexer_result.quality,
                imported=False,
                hash=nzo_id,
                usenet=True,
            )

            # Get initial status from SABnzbd
            torrent.status = self.get_torrent_status(torrent)
        except Exception:
            log.exception(f"Failed to download NZB {indexer_result.title}")
            raise

        return torrent

    def remove_torrent(self, torrent: Torrent, delete_data: bool = False) -> None:
        """
        Remove a torrent from SABnzbd.

        :param torrent: The torrent to remove.
        :param delete_data: Whether to delete the downloaded files.
        """
        try:
            self.client.delete_job(nzo_id=torrent.hash, delete_files=delete_data)
        except Exception:
            log.exception(f"Failed to remove torrent {torrent.title}")
            raise

    def pause_torrent(self, torrent: Torrent) -> None:
        """
        Pause a torrent in SABnzbd.

        :param torrent: The torrent to pause.
        """
        try:
            self.client.pause_job(nzo_id=torrent.hash)
        except Exception:
            log.exception(f"Failed to pause torrent {torrent.title}")
            raise

    def resume_torrent(self, torrent: Torrent) -> None:
        """
        Resume a paused torrent in SABnzbd.

        :param torrent: The torrent to resume.
        """
        try:
            self.client.resume_job(nzo_id=torrent.hash)
        except Exception:
            log.exception(f"Failed to resume torrent {torrent.title}")
            raise

    def get_torrent_status(self, torrent: Torrent) -> TorrentStatus:
        """
        Get the status of a specific download from SABnzbd.

        :param torrent: The torrent to get the status of.
        :return: The status of the torrent.
        """
        response = self.client.get_downloads(nzo_ids=torrent.hash)
        for slot in response.get("queue", {}).get("slots", []):
            if slot.get("nzo_id") == torrent.hash:
                return self._map_status(slot.get("status", "Unknown"))
        slot = self._history_slot(torrent)
        return self._map_status(slot.get("status", "Unknown"))

    def _history_slot(self, torrent: Torrent) -> dict:
        response = self.client.get_history(nzo_ids=torrent.hash)
        return next(
            (slot for slot in response.get("history", {}).get("slots", [])
             if slot.get("nzo_id") == torrent.hash), {}
        )

    def get_progress(self, torrents: list[Torrent]) -> dict:
        """Read live job progress without exposing remote paths or credentials."""
        if not torrents:
            return {}
        ids = [torrent.hash for torrent in torrents]
        queue = self.client.get_downloads(nzo_ids=ids, limit=len(ids)).get("queue", {})
        slots = {slot["nzo_id"]: slot for slot in queue.get("slots", [])}
        history_ids = set()
        missing = [identifier for identifier in ids if identifier not in slots]
        if missing:
            history = self.client.get_history(nzo_ids=missing, limit=len(missing))
            history_slots = {slot["nzo_id"]: slot for slot in history.get("history", {}).get("slots", [])}
            history_ids.update(history_slots)
            slots.update(history_slots)
        result = {}
        for torrent in torrents:
            slot = slots.get(torrent.hash, {})
            status = slot.get("status", "Unknown")
            in_history = torrent.hash in history_ids
            if in_history and status == "Queued":
                status = "PostProcessQueued"
            elif in_history and slot.get("loaded") is True and status in {"Unknown", "Downloading"}:
                status = "PostProcessing"
            if not in_history and queue.get("paused") and status in {"Downloading", "Queued"}:
                status = "QueuePaused"
            percent = None
            try:
                if slot.get("percentage") is not None:
                    percent = min(100.0, max(0.0, float(slot["percentage"])))
            except (TypeError, ValueError):
                pass
            if (in_history and status != "Failed") or status == "Completed" or torrent.imported:
                # History contains downloaded jobs waiting for/in post-processing.
                # This is download completion, not a fabricated processing percentage.
                percent = 100.0
            phase = "postprocessing" if in_history and status not in {"Completed", "Failed", "Unknown"} else "complete" if status == "Completed" else "download"
            result[str(torrent.id)] = {"percent": percent, "state": status, "phase": phase, "client": "SABnzbd", "usenet": True}
        return result

    def retry_download(self, torrent: Torrent) -> None:
        slots = self.client.get_downloads(nzo_ids=torrent.hash).get("queue", {}).get("slots", [])
        slot = next((slot for slot in slots if slot.get("nzo_id") == torrent.hash), None)
        if slot is not None:
            if slot.get("status") != "Paused":
                raise BadRequestError("Dieser Download läuft bereits oder wird nachbearbeitet.")
            self.client.resume_job(nzo_id=torrent.hash)
            return
        if self._history_slot(torrent).get("status") != "Failed":
            raise BadRequestError("Nur fehlgeschlagene Downloads können erneut versucht werden.")
        response = self.client.retry_item(nzo_id=torrent.hash)
        if not response.get("status"):
            raise BadRequestError("SABnzbd konnte den Download nicht erneut starten.")

    def get_download_path(self, torrent: Torrent) -> Path:
        """Use SAB's actual completed path; release names may be normalized."""
        storage = self._history_slot(torrent).get("storage")
        if not storage or not self.config.remote_download_directory:
            raise RuntimeError("SABnzbd meldet keinen zugeordneten Downloadpfad.")
        remote = Path(self.config.remote_download_directory)
        try:
            relative = Path(storage).relative_to(remote)
        except ValueError:
            raise RuntimeError("SABnzbd-Download liegt außerhalb des MediaManager-Ordners.") from None
        root = MediaManagerConfig().misc.torrent_directory.resolve()
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise RuntimeError("Ungültiger SABnzbd-Downloadpfad.")
        return target.parent if target.is_file() else target

    def _map_status(self, sabnzbd_status: str) -> TorrentStatus:
        """
        Map SABnzbd status to TorrentStatus.

        :param sabnzbd_status: The status from SABnzbd.
        :return: The corresponding TorrentStatus.
        """
        if sabnzbd_status in self.DOWNLOADING_STATE:
            return TorrentStatus.downloading
        if sabnzbd_status in self.FINISHED_STATE:
            return TorrentStatus.finished
        if sabnzbd_status in self.ERROR_STATE:
            return TorrentStatus.error
        return TorrentStatus.unknown
