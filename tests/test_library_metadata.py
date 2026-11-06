from types import SimpleNamespace as NS
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from media_manager.library_metadata import MetadataEdit, reconcile_seasons, load_metadata
from media_manager.library import catalogued_directories


def test_metadata_edit_validates_provider_identity_and_year():
    valid=dict(provider='tvdb',external_id=123,previous_provider='tvdb',previous_external_id=123,name='Own title',year=2026)
    assert MetadataEdit(**valid).year==2026
    for bad in [dict(provider='arbitrary'),dict(external_id=0),dict(year=9999),dict(name='')]:
        with pytest.raises(ValidationError):MetadataEdit(**(valid|bad))


def test_partial_catalogued_directories_do_not_reappear_as_unknown(tmp_path):
    root=tmp_path/'tv';root.mkdir();folder=root/'Own show';folder.mkdir();file=folder/'Season 1'/'Own.S01E01.mkv'
    assert catalogued_directories(root,[str(file),'/outside/Other/Episode.mkv'])=={folder}


def test_metadata_remapping_preserves_existing_internal_ids_and_numbered_links():
    eid,sid,files,requests,jobs=uuid4(),uuid4(),['original-file'],['own request'],['own job']
    episode=NS(id=eid,number=1,external_id=12,title='Old',air_date=None,jobs=jobs)
    season=NS(id=sid,number=1,external_id=11,name='Old',overview='',episodes=[episode],season_files=files,season_requests=requests)
    extra=NS(number=9,external_id=999,episodes=[NS(number=1,external_id=888)])
    row=NS(seasons=[season,extra],continuous_download=True,library='Own')
    fresh=NS(seasons=[NS(number=1,external_id=21,name='Correct season',overview='Details',episodes=[NS(number=1,external_id=22,title='Correct pilot',air_date=None)])])
    reconcile_seasons(row,fresh,True)
    assert season.id==sid and episode.id==eid
    assert season.external_id==21 and episode.external_id==22 and episode.title=='Correct pilot'
    assert season.season_files is files and season.season_requests is requests and episode.jobs is jobs
    assert row.continuous_download and row.library=='Own'
    assert extra.external_id==0 and extra.episodes[0].external_id==0


def test_provider_failure_returns_a_safe_error_without_leaking_details(monkeypatch):
    import media_manager.library_metadata as module
    module._cache.clear()
    def fail(**kwargs):raise RuntimeError('private source failure')
    monkeypatch.setattr(module,'get_metadata_provider',lambda provider:NS(get_show_metadata=fail))
    with pytest.raises(HTTPException) as error:load_metadata('tv','tmdb',123)
    assert error.value.status_code==502 and 'private source' not in error.value.detail
