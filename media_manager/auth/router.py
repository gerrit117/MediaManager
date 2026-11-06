from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi_users.router import get_oauth_router
from httpx_oauth.oauth2 import OAuth2
from sqlalchemy import select

from media_manager.auth.db import User
from media_manager.auth.schemas import AuthMetadata, UserRead
from media_manager.auth.users import (
    SECRET,
    create_default_admin_user,
    current_superuser,
    fastapi_users,
    openid_client,
    openid_cookie_auth_backend,
)
from media_manager.config import MediaManagerConfig
from media_manager.database import DbSessionDependency


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    await create_default_admin_user()
    yield


users_router = APIRouter(lifespan=lifespan)
auth_metadata_router = APIRouter()


def get_openid_router() -> APIRouter:
    if openid_client:
        return get_oauth_router(
            oauth_client=openid_client,
            backend=openid_cookie_auth_backend,
            get_user_manager=fastapi_users.get_user_manager,
            state_secret=SECRET,
            associate_by_email=False,
            is_verified_by_default=False,
            redirect_url=None,
        )
    # this is there, so that the appropriate routes are created even if OIDC is not configured,
    # e.g. for generating the frontend's openapi client
    return get_oauth_router(
        oauth_client=OAuth2(
            client_id="mock",
            client_secret="mock",  # noqa: S106
            authorize_endpoint="https://example.com/authorize",
            access_token_endpoint="https://example.com/token",  # noqa: S106
        ),
        backend=openid_cookie_auth_backend,
        get_user_manager=fastapi_users.get_user_manager,
        state_secret=SECRET,
        associate_by_email=False,
        is_verified_by_default=False,
        redirect_url=None,
    )


openid_config = MediaManagerConfig().auth.openid_connect


@users_router.get(
    "/users/all",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_superuser)],
)
def get_all_users(db: DbSessionDependency) -> list[UserRead]:
    stmt = select(User)
    result = db.execute(stmt).scalars().unique()
    return [UserRead.model_validate(user) for user in result]


@auth_metadata_router.get("/auth/metadata", status_code=status.HTTP_200_OK)
def get_auth_metadata() -> AuthMetadata:
    if openid_config.enabled:
        return AuthMetadata(oauth_providers=[openid_config.name])
    return AuthMetadata(oauth_providers=[])

# Server-managed fields stay out of UserUpdate: users cannot raise their own quota.
from pydantic import BaseModel, Field
from fastapi import HTTPException
from media_manager.auth.request_policy import usage_count, month_bounds
from media_manager.auth.users import current_active_user
from typing import Annotated
from uuid import UUID

class RequestPolicyUpdate(BaseModel):
    monthly_request_limit: int | None = Field(default=None,ge=0,le=100000)
    auto_approve_requests: bool = False

@users_router.get('/users/request-policies',dependencies=[Depends(current_superuser)])
def request_policies(db:DbSessionDependency):
    return [dict(id=str(u.id),monthly_request_limit=u.monthly_request_limit,auto_approve_requests=u.auto_approve_requests,used=usage_count(db,u.id),resets_at=month_bounds()[1]) for u in db.execute(select(User)).unique().scalars()]

@users_router.put('/users/{user_id}/request-policy',dependencies=[Depends(current_superuser)])
def update_request_policy(user_id:UUID,body:RequestPolicyUpdate,db:DbSessionDependency):
    user=db.execute(select(User).where(User.id==user_id).with_for_update(of=User)).unique().scalar_one_or_none()
    if user is None:raise HTTPException(404,'Benutzer nicht gefunden')
    user.monthly_request_limit=body.monthly_request_limit
    user.auto_approve_requests=body.auto_approve_requests
    db.flush()
    return {'saved':True}

@users_router.get('/requests/quota')
def own_quota(db:DbSessionDependency,user:Annotated[User,Depends(current_active_user)]):
    stored=db.get(User,user.id)
    return dict(limit=None if stored.is_superuser else stored.monthly_request_limit,used=usage_count(db,user.id),auto_approve=stored.is_superuser or stored.auto_approve_requests,resets_at=month_bounds()[1])

from pydantic import EmailStr
from fastapi_users.password import PasswordHelper
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from uuid import uuid4
import logging

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, repr=False)
    is_active: bool = True
    is_verified: bool = True
    is_superuser: bool = False
    monthly_request_limit: int | None = Field(default=None, ge=0, le=100000)
    auto_approve_requests: bool = False

@users_router.post('/users/admin-create', status_code=201, response_model=UserRead)
def create_user_as_admin(body: AdminUserCreate, db: DbSessionDependency,
                         actor: Annotated[User, Depends(current_superuser)]) -> UserRead:
    email = str(body.email).lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(409, 'Email address is already registered.')
    user = User(id=uuid4(), email=email,
                hashed_password=PasswordHelper().hash(body.password),
                is_active=body.is_active, is_verified=body.is_verified,
                is_superuser=body.is_superuser,
                monthly_request_limit=None if body.is_superuser else body.monthly_request_limit,
                auto_approve_requests=body.auto_approve_requests)
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Email address is already registered.') from None
    db.refresh(user)
    logging.getLogger(__name__).info('Administrator %s created account %s', actor.id, user.id)
    return UserRead.model_validate(user)
