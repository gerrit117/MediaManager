"""Monthly request accounting, enforced in the same transaction as insertion."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import HTTPException
from media_manager.database import Base

class RequestUsage(Base):
    __tablename__ = 'request_usage'
    id: Mapped[__import__('uuid').UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[__import__('uuid').UUID | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'),index=True)
    request_id: Mapped[__import__('uuid').UUID] = mapped_column(unique=True)
    scope_key: Mapped[str|None] = mapped_column(String(100),nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)


def month_bounds(now=None):
    local=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo('Europe/Berlin'))
    start=local.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    return start.astimezone(timezone.utc),end.astimezone(timezone.utc)


def usage_count(db,user_id,now=None):
    start,end=month_bounds(now)
    return db.scalar(select(func.count(func.distinct(func.coalesce(RequestUsage.scope_key,func.cast(RequestUsage.request_id,String))))).where(RequestUsage.user_id==user_id,RequestUsage.created_at>=start,RequestUsage.created_at<end)) or 0


def apply_request_policy(db,request,kind):
    from media_manager.auth.db import User
    if request.requested_by_id is None:return
    # Serializes movie and season submissions of the same user, even across workers.
    user=db.execute(select(User).where(User.id==request.requested_by_id).with_for_update(of=User)).unique().scalar_one()
    if not user.is_active:raise HTTPException(403,'Konto ist deaktiviert')
    scope_key=request_scope(db,request,kind)
    already_paid=db.scalar(select(RequestUsage.id).where(RequestUsage.user_id==user.id,RequestUsage.scope_key==scope_key).limit(1)) if scope_key else None
    if not already_paid and not user.is_superuser and user.monthly_request_limit is not None and usage_count(db,user.id)>=user.monthly_request_limit:
        raise HTTPException(429,'Monatliches Anfragekontingent ausgeschöpft. Es wird am ersten Tag des nächsten Monats (Europe/Berlin) erneuert.')
    request.authorized=bool(user.is_superuser or user.auto_approve_requests)
    request.authorized_by_id=user.id if request.authorized else None
    if not already_paid:db.add(RequestUsage(user_id=user.id,request_id=request.id,kind=kind,scope_key=scope_key))


def request_scope(db,request,kind):
    if kind=='movies' and getattr(request,'movie_id',None):return 'movie:'+str(request.movie_id)
    if kind=='tv' and getattr(request,'season_id',None):return 'season:'+str(request.season_id)
    if kind=='episodes' and getattr(request,'episode_id',None):
        from media_manager.tv.models import Episode
        season_id=db.scalar(select(Episode.season_id).where(Episode.id==request.episode_id))
        return 'season:'+str(season_id)
    return None
