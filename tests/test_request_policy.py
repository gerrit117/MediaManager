from datetime import datetime,timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock,patch
import pytest
from fastapi import HTTPException
from media_manager.auth.request_policy import month_bounds,apply_request_policy,RequestUsage
from media_manager.auth.schemas import UserUpdate,UserCreate

@pytest.mark.parametrize('now,start,end',[
 ('2026-03-31T23:00:00+00:00','2026-03-31T22:00:00+00:00','2026-04-30T22:00:00+00:00'),
 ('2026-12-31T23:30:00+00:00','2026-12-31T23:00:00+00:00','2027-01-31T23:00:00+00:00'),
 ('2026-10-25T02:00:00+00:00','2026-09-30T22:00:00+00:00','2026-10-31T23:00:00+00:00')])
def test_calendar_month_and_dst(now,start,end):
 bounds=month_bounds(datetime.fromisoformat(now));assert bounds==(datetime.fromisoformat(start),datetime.fromisoformat(end))

@pytest.mark.parametrize('limit,used,admin,auto,allowed,approved',[(1,0,False,False,True,False),(1,1,False,True,False,False),(0,0,False,False,False,False),(None,100,False,True,True,True),(0,100,True,False,True,True)])
def test_enforcement_and_approval(limit,used,admin,auto,allowed,approved):
 user=SimpleNamespace(id=uuid4(),is_active=True,is_superuser=admin,monthly_request_limit=limit,auto_approve_requests=auto)
 db=Mock();db.execute.return_value.unique.return_value.scalar_one.return_value=user
 request=SimpleNamespace(id=uuid4(),requested_by_id=user.id,authorized=False,authorized_by_id=None)
 with patch('media_manager.auth.request_policy.usage_count',return_value=used):
  if not allowed:
   with pytest.raises(HTTPException) as e:apply_request_policy(db,request,'movies')
   assert e.value.status_code==429;db.add.assert_not_called()
  else:
   apply_request_policy(db,request,'movies');assert request.authorized==approved
   assert isinstance(db.add.call_args.args[0],RequestUsage)
   assert request.authorized_by_id==(user.id if approved else None)

def test_user_cannot_update_or_register_policy_fields():
 data=dict(monthly_request_limit=None,auto_approve_requests=True)
 assert 'auto_approve_requests' not in UserUpdate(**data).model_dump()
 assert 'monthly_request_limit' not in UserCreate(email='test@example.com',password='123456789012',**data).model_dump()

def test_oidc_never_links_unverified_email():
 from media_manager.auth import router
 with patch.object(router,'openid_client',object()),patch.object(router,'get_oauth_router',return_value='route') as call:
  assert router.get_openid_router()=='route'
 assert call.call_args.kwargs['associate_by_email'] is False
 assert call.call_args.kwargs['is_verified_by_default'] is False

def test_magnet_redirect_preserved_for_download_client(tmp_path):
 from media_manager.indexer.schemas import IndexerQueryResult
 from media_manager.torrent.utils import get_torrent_hash
 from requests.exceptions import InvalidSchema
 magnet='magnet:?xt=urn:btih:'+'a'*40
 result=IndexerQueryResult(title='Own magnet regression',download_url='http://indexer.invalid/grab',seeders=0,flags=[],size=1,usenet=False,age=0,indexer='test')
 config=SimpleNamespace(misc=SimpleNamespace(torrent_directory=tmp_path),indexers=SimpleNamespace(prowlarr=SimpleNamespace(timeout_seconds=1)))
 with patch('media_manager.torrent.utils.MediaManagerConfig',return_value=config),patch('media_manager.torrent.utils.requests.get',side_effect=InvalidSchema),patch('media_manager.torrent.utils.follow_redirects_to_final_torrent_url',return_value=magnet):
  assert get_torrent_hash(result)=='a'*40
 assert result.download_url==magnet
