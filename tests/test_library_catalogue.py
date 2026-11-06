from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from media_manager.library import video_files, episode_numbers
from media_manager.movies.service import MovieService
from media_manager.tv.service import TvService


def test_catalogue_discovery_is_read_only_and_ignores_samples_archives_and_links(tmp_path):
    files = {'film.mkv': b'video', 'sample.mp4': b'sample', 'film.rar': b'archive', 'sub.srt': b'subtitle'}
    for name, content in files.items(): (tmp_path/name).write_bytes(content)
    outside=tmp_path.parent/'outside.mp4';outside.write_bytes(b'outside')
    (tmp_path/'link.mp4').symlink_to(outside)
    (tmp_path/'.hidden').mkdir();(tmp_path/'.hidden/extra.mp4').write_bytes(b'ignore')
    before={p.relative_to(tmp_path): (p.stat().st_ino,p.read_bytes()) for p in tmp_path.rglob('*') if p.is_file()}
    assert video_files(tmp_path)==[str(tmp_path/'film.mkv')]
    after={p.relative_to(tmp_path): (p.stat().st_ino,p.read_bytes()) for p in tmp_path.rglob('*') if p.is_file()}
    assert before==after


def test_episode_matching_is_conservative():
    assert episode_numbers(['Show.S01E01.mkv','Show.S01E02E03.mkv','Show.1x04.mp4','Show.S02E01.mkv','movie.2026.1080p.mkv'],1)=={1,2,3,4}


def test_catalogue_movie_keeps_file_and_tracks_disappearance(tmp_path):
    video=tmp_path/'original-name.mkv';video.write_bytes(b'video')
    repo=Mock();service=MovieService.__new__(MovieService);service.movie_repository=repo
    movie=SimpleNamespace(id=uuid4())
    assert service.catalogue_existing_movie(movie,tmp_path)
    entry=repo.add_movie_file.call_args.args[0]
    assert entry.source_files==[str(video)] and service.movie_file_exists_on_file(entry)
    assert video.read_bytes()==b'video'
    video.unlink()
    assert not service.movie_file_exists_on_file(entry)
    assert not service.catalogue_existing_movie(movie,tmp_path)


def test_partial_season_is_recorded_but_not_marked_complete(tmp_path):
    one=tmp_path/'Show.S01E01.mkv';one.write_bytes(b'video')
    season=SimpleNamespace(id=uuid4(),number=1,episodes=[SimpleNamespace(number=1),SimpleNamespace(number=2)])
    repo=Mock();repo.get_season.return_value=season
    service=TvService.__new__(TvService);service.tv_repository=repo
    assert service.catalogue_existing_tv_show(SimpleNamespace(seasons=[season]),tmp_path)
    entry=repo.add_season_file.call_args.args[0]
    assert not service.season_file_exists_on_file(entry)
    two=tmp_path/'Show.S01E02.mkv';two.write_bytes(b'video')
    service.catalogue_existing_tv_show(SimpleNamespace(seasons=[season]),tmp_path)
    entry=repo.add_season_file.call_args.args[0]
    assert service.season_file_exists_on_file(entry)
    one.unlink()
    assert not service.season_file_exists_on_file(entry)


def test_fast_discovery_does_not_query_metadata(tmp_path, monkeypatch):
    folder=tmp_path/'Own unrecognised film';folder.mkdir();(folder/'film.mkv').write_bytes(b'video')
    monkeypatch.setattr('media_manager.movies.service.MediaManagerConfig', lambda:SimpleNamespace(misc=SimpleNamespace(movie_directory=tmp_path)))
    monkeypatch.setattr('media_manager.movies.service.get_importable_media_directories', lambda root:[folder])
    service=MovieService.__new__(MovieService);service.movie_repository=Mock()
    service.movie_repository.catalogued_source_files.return_value=[]
    service.get_import_candidates=Mock(side_effect=AssertionError('metadata lookup must be deferred'))
    result=service.get_importable_movies(Mock(),discover_only=True)
    assert len(result)==1 and result[0].directory==folder and result[0].candidates==[]
    service.get_import_candidates.assert_not_called()
