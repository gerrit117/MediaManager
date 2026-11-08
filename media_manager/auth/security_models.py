from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import ForeignKey,DateTime,String,Boolean,Integer
from sqlalchemy.orm import Mapped,mapped_column
from media_manager.database import Base
class Invitation(Base):
    __tablename__='account_invitation'
    id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    digest:Mapped[str]=mapped_column(String(64),unique=True)
    email:Mapped[str|None]=mapped_column(nullable=True)
    created_by_id:Mapped[UUID|None]=mapped_column(ForeignKey('user.id',ondelete='SET NULL'))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    used_by_id:Mapped[UUID|None]=mapped_column(ForeignKey('user.id',ondelete='SET NULL'),nullable=True)
    used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class SecurityRate(Base):
    __tablename__='account_security_rate'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
