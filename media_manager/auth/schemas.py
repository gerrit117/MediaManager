import uuid
from typing import Literal

from fastapi_users import schemas
from pydantic import BaseModel


class UserRead(schemas.BaseUser[uuid.UUID]):
    preferred_language: Literal["de", "en"] | None = None
    monthly_request_limit: int | None = None
    auto_approve_requests: bool = False


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    preferred_language: Literal["de", "en"] | None = None


class AuthMetadata(BaseModel):
    oauth_providers: list[str]
    email_available: bool = False
    invitation_required: bool = True
