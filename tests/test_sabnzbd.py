import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from media_manager.exceptions import InvalidConfigError
from media_manager.torrent.download_clients.sabnzbd import SabnzbdDownloadClient
from media_manager.torrent.manager import DownloadManager
from media_manager.torrent.schemas import TorrentStatus


class SabnzbdTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(SabnzbdDownloadClient)
        self.client.client = Mock()
        self.client.config = SimpleNamespace(category='mediamanager',remote_download_directory='/remote/mediamanager')
        self.torrent = SimpleNamespace(hash='job-1')

    def test_job_status_not_global_status(self):
        self.client.client.get_downloads.return_value={'queue':{'status':'Downloading','slots':[{'nzo_id':'job-1','status':'Paused'}]}}
        self.assertEqual(self.client.get_torrent_status(self.torrent),TorrentStatus.downloading)
        self.client.client.get_history.assert_not_called()

    def test_completed_job_looked_up_in_history(self):
        self.client.client.get_downloads.return_value={'queue':{'status':'Idle','slots':[]}}
        self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-1','status':'Completed'}]}}
        self.assertEqual(self.client.get_torrent_status(self.torrent),TorrentStatus.finished)

    def test_other_job_cannot_mark_this_one_complete(self):
        self.client.client.get_downloads.return_value={'queue':{'status':'Downloading','slots':[{'nzo_id':'other','status':'Completed'}]}}
        self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'other','status':'Completed'}]}}
        self.assertEqual(self.client.get_torrent_status(self.torrent),TorrentStatus.unknown)

    def test_failed_job_from_history(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[]}}
        self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-1','status':'Failed'}]}}
        self.assertEqual(self.client.get_torrent_status(self.torrent),TorrentStatus.error)

    def test_actual_normalized_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);actual=root/'A normalized release';actual.mkdir();file=actual/'video.mkv';file.touch()
            self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-1','storage':'/remote/mediamanager/A normalized release/video.mkv'}]}}
            with patch('media_manager.torrent.download_clients.sabnzbd.MediaManagerConfig',return_value=SimpleNamespace(misc=SimpleNamespace(torrent_directory=root))):
                self.assertEqual(self.client.get_download_path(self.torrent),actual)

    def test_remote_path_escape_rejected(self):
        for storage in ['/remote/other/video.mkv','/remote/mediamanager/../../etc/passwd']:
            with self.subTest(storage=storage),tempfile.TemporaryDirectory() as tmp:
                self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-1','storage':storage}]}}
                with patch('media_manager.torrent.download_clients.sabnzbd.MediaManagerConfig',return_value=SimpleNamespace(misc=SimpleNamespace(torrent_directory=Path(tmp)))):
                    with self.assertRaises(RuntimeError):self.client.get_download_path(self.torrent)

    def test_missing_download_manager_has_useful_error(self):
        manager=object.__new__(DownloadManager);manager._usenet_client=None;manager._torrent_client=None
        with self.assertRaisesRegex(InvalidConfigError,'SABnzbd'):
            manager._get_appropriate_client(SimpleNamespace(usenet=True))

    def test_submission_uses_dedicated_category_and_unpack(self):
        from media_manager.indexer.schemas import IndexerQueryResult
        release=IndexerQueryResult(title='Own Test 1080p',download_url='http://localhost/test.nzb',seeders=0,flags=[],size=1,usenet=True,age=0,indexer='test')
        self.client.client.add_uri.return_value={'status':True,'nzo_ids':['job-1']}
        self.client.client.get_downloads.return_value={'queue':{'slots':[{'nzo_id':'job-1','status':'Queued'}]}}
        result=self.client.download_torrent(release)
        self.client.client.add_uri.assert_called_once_with(url='http://localhost/test.nzb',nzbname='Own Test 1080p',cat='mediamanager',pp=3)
        self.assertEqual(result.hash,'job-1')

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.client=object.__new__(SabnzbdDownloadClient)
        self.client.client=Mock()
        self.job=SimpleNamespace(id='job-id',hash='job-hash',imported=False)

    def test_progress_is_for_our_job_only(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[{'nzo_id':'job-hash','status':'Downloading','percentage':'42.6'},{'nzo_id':'foreign','status':'Completed','percentage':'100'}]}}
        result=self.client.get_progress([self.job])
        self.assertEqual(result,{'job-id':{'percent':42.6,'state':'Downloading','client':'SABnzbd','usenet':True}})
        self.client.client.get_history.assert_not_called()

    def test_completed_history_progress(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[]}}
        self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-hash','status':'Completed'}]}}
        self.assertEqual(self.client.get_progress([self.job])['job-id']['percent'],100)

    def test_missing_or_invalid_progress_not_invented(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[{'nzo_id':'job-hash','status':'Downloading','percentage':'broken'}]}}
        self.assertIsNone(self.client.get_progress([self.job])['job-id']['percent'])

    def test_global_pause_not_presented_as_per_job_resume(self):
        self.client.client.get_downloads.return_value={'queue':{'paused':True,'slots':[{'nzo_id':'job-hash','status':'Downloading','percentage':'9'}]}}
        self.assertEqual(self.client.get_progress([self.job])['job-id']['state'],'QueuePaused')

    def test_running_job_cannot_be_retried(self):
        from media_manager.exceptions import BadRequestError
        self.client.client.get_downloads.return_value={'queue':{'slots':[{'nzo_id':'job-hash','status':'Downloading'}]}}
        with self.assertRaises(BadRequestError):self.client.retry_download(self.job)
        self.client.client.resume_job.assert_not_called()
        self.client.client.retry_item.assert_not_called()

    def test_paused_job_is_resumed_without_readding_it(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[{'nzo_id':'job-hash','status':'Paused'}]}}
        self.client.retry_download(self.job)
        self.client.client.resume_job.assert_called_once_with(nzo_id='job-hash')
        self.client.client.retry_item.assert_not_called()

    def test_only_failed_history_job_can_be_retried(self):
        self.client.client.get_downloads.return_value={'queue':{'slots':[]}}
        self.client.client.get_history.return_value={'history':{'slots':[{'nzo_id':'job-hash','status':'Failed'}]}}
        self.client.client.retry_item.return_value={'status':True}
        self.client.retry_download(self.job)
        self.client.client.retry_item.assert_called_once_with(nzo_id='job-hash')

if __name__=='__main__':unittest.main()
