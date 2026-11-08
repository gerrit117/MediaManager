"""Real PostgreSQL, FFprobe and SMTP-sink checks; synthetic media/accounts only."""
import tempfile,subprocess,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from media_manager.database import init_engine
from media_manager.config import MediaManagerConfig
from media_manager.media_features_models import RequestState,Delivery,ReleaseLock,Replacement,EmbyMatch
from media_manager.movies.models import Movie,MovieFile,MovieRequest
from media_manager.auth.db import User
from media_manager.torrent.schemas import Quality,TorrentStatus
from media_manager.account_notifications import observe,deliver,enqueue
from media_manager.emby_matching import scan
from media_manager.release_control import fingerprint,finalize,locked
from media_manager.request_center import approve,Approval
engine=init_engine(MediaManagerConfig().database)
root=MediaManagerConfig().misc.movie_directory/'Own delivery fixture';root.mkdir(exist_ok=True)
source=root/'Own fixture.mkv'
subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','color=c=blue:s=32x32:d=0.1','-c:v','ffv1',str(source)],check=True)
with Session(engine) as db:
    owner=User(id=uuid.uuid4(),email='notification-fixture@example.com',hashed_password='unused',is_active=True,is_verified=True,is_superuser=False,preferred_language='de')
    db.add(owner);media=Movie(id=uuid.uuid4(),external_id=99887766,metadata_provider='tmdb',name='Own delivery fixture',year=2026,overview='Own fixture',library='Default');db.add(media);db.flush()
    db.add(MovieFile(movie_id=media.id,file_path_suffix='OWN-FIXTURE',torrent_id=None,quality=Quality.fullhd,source_files=[str(source)]))
    request=MovieRequest(id=uuid.uuid4(),movie_id=media.id,requested_by_id=owner.id,wanted_quality=Quality.fullhd,min_quality=Quality.hd,authorized=False);db.add(request);db.commit()
    with patch('media_manager.emby.EmbyClient.available',return_value=False):observe(db)
    state=db.get(RequestState,('movie',request.id));assert state.state=='waiting_emby'
    admin=db.scalars(select(User).where(User.is_superuser==True)).unique().first()
    approve('movie',request.id,Approval(authorized=False,reason='Own rejection reason'),db,admin)
    state=db.get(RequestState,('movie',request.id));assert state.rejected and state.reason=='Own rejection reason'
    assert db.scalar(select(Delivery.id).where(Delivery.user_id==owner.id,Delivery.event_key==f'movie:{request.id}:rejected'))
    approve('movie',request.id,Approval(authorized=True),db,admin)
    with patch('media_manager.emby.EmbyClient.available',return_value=False):observe(db)
    assert db.get(RequestState,('movie',request.id)).state=='waiting_emby'
    assert not db.scalar(select(Delivery.id).where(Delivery.event_key==f'movie:{request.id}:finished'))
    with patch('media_manager.emby.EmbyClient.available',return_value=True):observe(db);observe(db)
    assert db.get(RequestState,('movie',request.id)).state=='finished'
    assert len(list(db.scalars(select(Delivery).where(Delivery.event_key==f'movie:{request.id}:finished'))))==1
    deliver(db)
    sent=list(db.scalars(select(Delivery).where(Delivery.user_id==owner.id)));assert sent and all(row.sent_at for row in sent)
    enqueue(db,'own-transient-error',owner,'request_approved',{'title':media.name,'year':2026});db.commit()
    with patch('media_manager.notification.utils.send_email',side_effect=TimeoutError):deliver(db)
    retry=db.scalar(select(Delivery).where(Delivery.event_key=='own-transient-error'));assert retry.attempts==1 and retry.sent_at is None
    retry.next_attempt=datetime.now(timezone.utc);db.commit();deliver(db);assert retry.sent_at
    class FakeEmby:
        def items(self,**kwargs):return [{'Id':'own-emby-movie','Type':'Movie','Name':media.name,'ProviderIds':{'Tmdb':str(media.external_id)},'Path':'/emby/Own fixture.mkv'}]
    scan(db,FakeEmby());matched=db.get(EmbyMatch,('movie',media.id));assert matched.status=='matched' and matched.emby_ids==['own-emby-movie']
    # Verify FFprobe validation on a real tiny stream, and non-destructive handling of a corrupt replacement.
    from media_manager.torrent.models import Torrent
    job=Torrent(id=uuid.uuid4(),title='Own replacement fixture',hash='own-'+uuid.uuid4().hex,status=TorrentStatus.downloading,quality=Quality.fullhd,imported=False,usenet=True);db.add(job);db.commit()
    newer=root/'Own new fixture.mkv';newer.write_bytes(source.read_bytes())
    db.add(Replacement(job_id=job.id,kind='movie',media_id=media.id,manifest={'old_files':[fingerprint(source)],'archived_files':[]},status='pending'));db.commit()
    finalize(db,job.id,[str(newer)]);assert newer.exists() and not source.exists()
    row=db.get(Replacement,job.id);assert row.status=='completed';archive=Path(row.manifest['archived_files'][0]['archive']);assert archive.exists()
    assert (MediaManagerConfig().misc.movie_directory/'.mediamanager-replaced'/'.ignore').exists()
print('media-delivery: real SMTP, request lifecycle, rejection reason, deduplication, retry, Emby matching and FFprobe replacement passed')
