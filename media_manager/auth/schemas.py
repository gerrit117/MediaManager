import uuid

from fastapi_users import schemas
from pydantic import BaseModel


class UserRead(schemas.BaseUser[uuid.UUID]):
    monthly_request_limit: int | None = None
    auto_approve_requests: bool = False


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class AuthMetadata(BaseModel):
    oauth_providers: list[str]
