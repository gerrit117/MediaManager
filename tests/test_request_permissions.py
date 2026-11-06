from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from media_manager.movies.router import update_movie_request
from media_manager.tv.router import update_request
from media_manager.movies.schemas import MovieRequestBase
from media_manager.tv.schemas import UpdateSeasonRequest
from media_manager.torrent.schemas import Quality

@pytest.mark.parametrize('kind',['movie','season'])
@pytest.mark.parametrize('who',['owner','other','admin'])
def test_edit_owner_or_admin_only_and_preserve_approval(kind,who):
 owner=uuid4();approval=object();request=SimpleNamespace(id=uuid4(),requested_by=SimpleNamespace(id=owner),authorized=True,authorized_by=approval,season_id=uuid4(),min_quality=Quality.sd,wanted_quality=Quality.hd)
 user=SimpleNamespace(id=owner if who=='owner' else uuid4(),is_superuser=who=='admin')
 service=Mock();service.get_movie_request_by_id.return_value=request;service.get_season_request_by_id.return_value=request
 def run():
  if kind=='movie':return update_movie_request(service,request.id,MovieRequestBase(min_quality=Quality.hd,wanted_quality=Quality.fullhd),user)
  return update_request(service,user,UpdateSeasonRequest(id=request.id,min_quality=Quality.hd,wanted_quality=Quality.fullhd))
 if who=='other':
  with pytest.raises(HTTPException) as e:run()
  assert e.value.status_code==403
  service.update_movie_request.assert_not_called();service.update_season_request.assert_not_called()
 else:
  run();assert request.min_quality==Quality.hd
  assert request.requested_by.id==owner and request.authorized and request.authorized_by is approval

@pytest.mark.parametrize('kind',['movie','season'])
def test_missing_request_404(kind):
 service=Mock();service.get_movie_request_by_id.return_value=None;service.get_season_request_by_id.return_value=None
 user=SimpleNamespace(id=uuid4(),is_superuser=False)
 with pytest.raises(HTTPException) as e:
  if kind=='movie':update_movie_request(service,uuid4(),MovieRequestBase(min_quality=Quality.hd,wanted_quality=Quality.fullhd),user)
  else:update_request(service,user,UpdateSeasonRequest(id=uuid4(),min_quality=Quality.hd,wanted_quality=Quality.fullhd))
 assert e.value.status_code==404
