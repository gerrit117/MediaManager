from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from media_manager.indexer.schemas import IndexerQueryResult
from media_manager.indexer.utils import _keyword_matches
from media_manager.torrent.utils import validate_file_path_suffix
from media_manager.exceptions import BadRequestError
from media_manager.torrent.schemas import Quality,TorrentStatus,Torrent
from media_manager.torrent.download_clients.qbittorrent import QbittorrentDownloadClient
from media_manager.torrent.download_clients.transmission import TransmissionDownloadClient
from media_manager.torrent.manager import DownloadManager

def release(title='Own Test 1080p',usenet=False):
 return IndexerQueryResult(title=title,download_url='magnet:?xt=urn:btih:'+'1'*40,seeders=0,flags=[],size=1,usenet=usenet,age=0,indexer='offline')

@pytest.mark.parametrize('title,expected',[('Film.2160p',Quality.uhd),('Film.UHD',Quality.uhd),('Film.4K',Quality.uhd),('Film.Full-HD',Quality.fullhd),('Film.1080p',Quality.fullhd),('Film.720p',Quality.hd),('Film.SD',Quality.sd)])
def test_quality(title,expected):assert release(title).quality==expected

@pytest.mark.parametrize('keyword,title,expected',[('CAM','Cambridge.1080p',False),('CAM','Movie.CAM.720p',True),('DD+','Movie.DD+.German',True),('German','Movie.GERMAN.DL',True),('German','Movie.Germany',False),('','Movie',False)])
def test_scoring_boundaries(keyword,title,expected):assert _keyword_matches(keyword,title)==expected

@pytest.mark.parametrize('suffix',['../outside','../../file','/tmp/test','x\\..\\file','x\x00','a:b','x'*129])
def test_suffix_rejects_paths(suffix):
 with pytest.raises(BadRequestError):validate_file_path_suffix(suffix)

@pytest.mark.parametrize('suffix',['','1080p','Deutsch + Englisch','Director’s Cut [HDR]','DD+ 5.1'])
def test_valid_suffix_unchanged(suffix):assert validate_file_path_suffix(suffix)==suffix

@pytest.mark.parametrize('answer',['Ok.',{'pending_count':1},SimpleNamespace(success_count=1,pending_count=0)])
def test_qbit_old_and_new_responses(answer):
 client=object.__new__(QbittorrentDownloadClient);client.config=SimpleNamespace(category_name='Custom Category');client.api_client=Mock();client.api_client.torrents_add.return_value=answer
 client.get_torrent_status=Mock(return_value=TorrentStatus.downloading)
 with patch('media_manager.torrent.download_clients.qbittorrent.get_torrent_hash',return_value='1'*40):job=client.download_torrent(release())
 assert job.usenet is False
 assert client.api_client.torrents_add.call_args.kwargs['category']=='Custom Category'

@pytest.mark.parametrize('answer',['Fails.',{'pending_count':0,'success_count':0},None])
def test_qbit_rejected_response(answer):
 client=object.__new__(QbittorrentDownloadClient);client.config=SimpleNamespace(category_name='test');client.api_client=Mock();client.api_client.torrents_add.return_value=answer
 with patch('media_manager.torrent.download_clients.qbittorrent.get_torrent_hash',return_value='1'*40),pytest.raises(RuntimeError):client.download_torrent(release())

@pytest.mark.parametrize('state,percent,expected',[('stoppedDL',.4,'Paused'),('downloading',.42,'Downloading'),('uploading',1,'Completed'),('error',0,'Failed')])
def test_qbit_progress(state,percent,expected):
 client=object.__new__(QbittorrentDownloadClient);client.api_client=Mock();job=Torrent(status=TorrentStatus.downloading,title='own',quality=Quality.hd,imported=False,hash='1'*40)
 client.api_client.torrents_info.return_value=[{'hash':job.hash,'state':state,'progress':percent}]
 result=client.get_progress([job])[str(job.id)]
 assert result['state']==expected and result['percent']==percent*100 and result['usenet'] is False

@pytest.mark.parametrize('state,percent,expected',[('stopped',.4,'Paused'),('downloading',.42,'Downloading'),('seeding',1,'Completed'),('stopped',1,'Completed')])
def test_transmission_progress(state,percent,expected):
 client=object.__new__(TransmissionDownloadClient);client._client=Mock();job=Torrent(status=TorrentStatus.downloading,title='own',quality=Quality.hd,imported=False,hash='1'*40)
 client._client.get_torrents.return_value=[SimpleNamespace(hash_string=job.hash,status=state,percent_done=percent,error=0)]
 result=client.get_progress([job])[str(job.id)];assert result['state']==expected and result['percent']==percent*100

@pytest.mark.parametrize('usenet',[True,False])
def test_manager_keeps_protocols_separate(usenet):
 manager=object.__new__(DownloadManager);manager._torrent_client=Mock();manager._usenet_client=Mock()
 manager.download(release(usenet=usenet))
 wanted=manager._usenet_client if usenet else manager._torrent_client;other=manager._torrent_client if usenet else manager._usenet_client
 wanted.download_torrent.assert_called_once();other.download_torrent.assert_not_called()

def test_custom_movie_search_still_applies_scoring():
 from media_manager.movies.service import MovieService
 service=object.__new__(MovieService);service.indexer_service=Mock();movie=SimpleNamespace(library='Default')
 with patch('media_manager.movies.service.evaluate_indexer_query_results',return_value=[]) as evaluate:
  service.get_all_available_torrents_for_movie(movie,'Own custom query')
  evaluate.assert_called_once()

def test_invalid_movie_suffix_rejected_before_download():
 from media_manager.movies.service import MovieService
 service=object.__new__(MovieService);service.indexer_service=Mock();service.torrent_service=Mock()
 with pytest.raises(BadRequestError):service.download_torrent(None,None,'../outside')
 service.torrent_service.download.assert_not_called()
