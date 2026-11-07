"""Provider aliases, individual episode requests and cached movie collections."""
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from media_manager.database import Base
from media_manager.torrent.schemas import Quality

class ShowExternalId(Base):
    __tablename__='show_external_id'
    provider: Mapped[str]=mapped_column(primary_key=True)
    external_id: Mapped[str]=mapped_column(primary_key=True)
    show_id: Mapped[UUID]=mapped_column(ForeignKey('show.id',ondelete='CASCADE'),index=True)

class EpisodeRequest(Base):
    __tablename__='episode_request'
    __table_args__=(UniqueConstraint('episode_id','wanted_quality'),)
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    episode_id: Mapped[UUID]=mapped_column(ForeignKey('episode.id',ondelete='CASCADE'),index=True)
    requested_by_id: Mapped[UUID|None]=mapped_column(ForeignKey('user.id',ondelete='SET NULL'))
    authorized_by_id: Mapped[UUID|None]=mapped_column(ForeignKey('user.id',ondelete='SET NULL'))
    authorized: Mapped[bool]=mapped_column(default=False)
    min_quality: Mapped[Quality]
    wanted_quality: Mapped[Quality]

class MovieCollection(Base):
    __tablename__='movie_collection'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]
    overview: Mapped[str]=mapped_column(default='')
    poster_url: Mapped[str|None]
    parts: Mapped[list]=mapped_column(JSON,default=list)
    source: Mapped[str]
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
