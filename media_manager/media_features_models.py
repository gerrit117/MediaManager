"""Persistent release protection, replacement manifests and per-account delivery state."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import JSON, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from media_manager.database import Base

class ReleaseLock(Base):
    __tablename__='release_lock'
    kind:Mapped[str]=mapped_column(String(12),primary_key=True)
    media_id:Mapped[UUID]=mapped_column(primary_key=True)

class Replacement(Base):
    __tablename__='release_replacement'
    job_id:Mapped[UUID]=mapped_column(ForeignKey('torrent.id',ondelete='CASCADE'),primary_key=True)
    kind:Mapped[str]=mapped_column(String(12))
    media_id:Mapped[UUID]
    manifest:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(String(20),default='pending')

class NotificationPreference(Base):
    __tablename__='account_notification_preference'
    user_id:Mapped[UUID]=mapped_column(ForeignKey('user.id',ondelete='CASCADE'),primary_key=True)
    categories:Mapped[dict]=mapped_column(JSON,default=dict)

class PushSubscription(Base):
    __tablename__='account_push_subscription'
    id:Mapped[UUID]=mapped_column(primary_key=True)
    user_id:Mapped[UUID]=mapped_column(ForeignKey('user.id',ondelete='CASCADE'),index=True)
    endpoint_hash:Mapped[str]=mapped_column(String(64),unique=True)
    subscription:Mapped[dict]=mapped_column(JSON)

class RequestState(Base):
    __tablename__='request_notification_state'
    kind:Mapped[str]=mapped_column(String(12),primary_key=True)
    request_id:Mapped[UUID]=mapped_column(primary_key=True)
    state:Mapped[str]=mapped_column(String(20))
    rejected:Mapped[bool]=mapped_column(default=False)
    reason:Mapped[str|None]
    emby_available:Mapped[bool|None]
    first_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class Delivery(Base):
    __tablename__='account_notification_delivery'
    __table_args__=(UniqueConstraint('event_key','user_id','channel'),)
    id:Mapped[UUID]=mapped_column(primary_key=True)
    event_key:Mapped[str]=mapped_column(String(200))
    user_id:Mapped[UUID]=mapped_column(ForeignKey('user.id',ondelete='CASCADE'))
    channel:Mapped[str]=mapped_column(String(10))
    payload:Mapped[dict]=mapped_column(JSON)
    attempts:Mapped[int]=mapped_column(default=0)
    next_attempt:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    sent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error:Mapped[str|None]

class EmbyMatch(Base):
    __tablename__='emby_media_match'
    kind:Mapped[str]=mapped_column(String(12),primary_key=True)
    media_id:Mapped[UUID]=mapped_column(primary_key=True)
    status:Mapped[str]=mapped_column(String(24))
    emby_ids:Mapped[list]=mapped_column(JSON,default=list)
    evidence:Mapped[dict]=mapped_column(JSON,default=dict)
    checked_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
