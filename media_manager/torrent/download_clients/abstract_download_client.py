from abc import ABC, abstractmethod

from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.torrent.schemas import Torrent, TorrentStatus


class AbstractDownloadClient(ABC):
    """
    Abstract base class for download clients.
    Defines the interface that all download clients must implement.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def download_torrent(self, indexer_result: IndexerQueryResult) -> Torrent:
        """
        Add a torrent to the download client and return the torrent object.

        :param indexer_result: The indexer query result of the torrent file to download.
        :return: The torrent object with calculated hash and initial status.
        """

    @abstractmethod
    def remove_torrent(self, torrent: Torrent, delete_data: bool = False) -> None:
        """
        Remove a torrent from the download client.

        :param torrent: The torrent to remove.
        :param delete_data: Whether to delete the downloaded data.
        """

    @abstractmethod
    def get_torrent_status(self, torrent: Torrent) -> TorrentStatus:
        """
        Get the status of a specific torrent.

        :param torrent: The torrent to get the status of.
        :return: The status of the torrent.
        """

    @abstractmethod
    def pause_torrent(self, torrent: Torrent) -> None:
        """
        Pause a torrent download.

        :param torrent: The torrent to pause.
        """

    @abstractmethod
    def resume_torrent(self, torrent: Torrent) -> None:
        """
        Resume a torrent download.

        :param torrent: The torrent to resume.
        """

    def get_progress(self, torrents: list[Torrent]) -> dict:
        return {}

    def retry_download(self, torrent: Torrent) -> None:
        from media_manager.exceptions import BadRequestError

        state = self.get_progress([torrent]).get(str(torrent.id), {}).get('state')
        if state not in {'Paused', 'Failed'}:
            raise BadRequestError('Dieser Download kann derzeit nicht fortgesetzt oder erneut versucht werden.')
        self.resume_torrent(torrent)
