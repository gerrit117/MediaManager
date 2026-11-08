"""Single-use five-character invitations. Codes and mail tokens are never logged."""
import hashlib,hmac,secrets,string,time
from datetime import datetime,timedelta,timezone
from typing import Annotated
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,EmailStr,Field
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from fastapi_users.password import PasswordHelper
from media_manager.database import DbSessionDependency
from media_manager.auth.db import User
from media_manager.auth.users import current_superuser
from media_manager.auth.schemas import UserRead
from media_manager.auth.security_models import Invitation,SecurityRate
from media_manager.auth.password_policy import validate_password
from media_manager.auth.mail import mail_ready,send_verification,notify_admins
from media_manager.config import MediaManagerConfig
router=APIRouter()

def digest(value):
    from media_manager.auth.users import SECRET
    return hmac.new(SECRET.encode(),value.encode(),hashlib.sha256).hexdigest()
def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def rate_limit(db,request,purpose,maximum=10,window=900):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    now=datetime.now(timezone.utc);bucket=int(time.time())//window
    client='all' if purpose.endswith('-global') else request.client.host if request.client else 'unknown'
    key=digest(f'{purpose}:{client}:{bucket}')
    factory=sqlite_insert if db.get_bind().dialect.name=='sqlite' else pg_insert
    stmt=factory(SecurityRate).values(key=key,attempts=1,expires_at=now+timedelta(seconds=window*2))
    count=db.scalar(stmt.on_conflict_do_update(index_elements=['key'],set_={'attempts':SecurityRate.attempts+1}).returning(SecurityRate.attempts));db.commit()
    if count>maximum:raise HTTPException(429,'Too many attempts. Please try again later.')

class InvitationCreate(BaseModel):
    email:EmailStr|None=None
    valid_days:int=Field(7,ge=1,le=30)
class Register(BaseModel):
    email:EmailStr
    password:str=Field(repr=False,max_length=1024)
    invitation_code:str=Field(min_length=5,max_length=5,pattern=r'^[A-Z0-9]{5}$')

@router.get('/users/invitations',dependencies=[Depends(current_superuser)])
def invitations(db:DbSessionDependency):
    return [dict(id=str(i.id),email=i.email,expires_at=i.expires_at,used_at=i.used_at,revoked=i.revoked) for i in db.scalars(select(Invitation).order_by(Invitation.expires_at.desc()).limit(100))]

@router.post('/users/invitations',status_code=201)
def create_invitation(body:InvitationCreate,db:DbSessionDependency,user:Annotated[User,Depends(current_superuser)]):
    if not mail_ready():raise HTTPException(503,'Configure SMTP before inviting users.')
    db.execute(delete(SecurityRate).where(SecurityRate.expires_at<datetime.now(timezone.utc)))
    for _ in range(5):
        code=''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(5))
        row=Invitation(id=uuid4(),digest=digest(code),email=str(body.email).lower() if body.email else None,created_by_id=user.id,expires_at=datetime.now(timezone.utc)+timedelta(days=body.valid_days))
        try:db.add(row);db.commit();return {'id':str(row.id),'code':code,'expires_at':row.expires_at}
        except IntegrityError:db.rollback()
    raise HTTPException(503,'Could not create invitation. Please try again.')

@router.delete('/users/invitations/{invitation_id}',status_code=204,dependencies=[Depends(current_superuser)])
def revoke(invitation_id:UUID,db:DbSessionDependency):
    row=db.get(Invitation,invitation_id)
    if row is None:raise HTTPException(404,'Invitation not found.')
    row.revoked=True;db.commit()

@router.post('/auth/register',status_code=201,response_model=UserRead)
def register(body:Register,request:Request,db:DbSessionDependency):
    rate_limit(db,request,'register');rate_limit(db,request,'register-global',maximum=300,window=3600)
    if not mail_ready():raise HTTPException(503,'Registration requires configured SMTP email delivery.')
    try:validate_password(body.password)
    except ValueError as e:raise HTTPException(400,str(e)) from None
    invite=db.scalars(select(Invitation).where(Invitation.digest==digest(body.invitation_code)).with_for_update()).first()
    email=str(body.email).lower();now=datetime.now(timezone.utc)
    if not invite or invite.revoked or invite.used_at or aware(invite.expires_at)<=now or (invite.email and invite.email!=email):raise HTTPException(400,'Invitation code is invalid, expired or already used.')
    user=User(id=uuid4(),email=email,hashed_password=PasswordHelper().hash(body.password),is_active=True,is_verified=False,is_superuser=False,monthly_request_limit=10,auto_approve_requests=False)
    try:
        db.add(user);db.flush();invite.used_at=now;invite.used_by_id=user.id;db.commit()
    except IntegrityError:db.rollback();raise HTTPException(400,'Registration could not be completed. Try signing in or contact the administrator.') from None
    send_verification(user);notify_admins('New account','A new invited account awaits email confirmation: '+email)
    return UserRead.model_validate(user)

# Applied to the framework's recovery and verification routers.
def public_mail_rate(request:Request,db:DbSessionDependency):
    rate_limit(db,request,'account-mail')
    if request.url.path.endswith(('forgot-password','request-verify-token')) and not mail_ready():raise HTTPException(503,'Account email delivery is not configured. Contact the administrator.')
