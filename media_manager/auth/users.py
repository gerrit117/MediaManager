import contextlib
import json
from media_manager.configuration import config_file
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any, override

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx_oauth.clients.openid import OpenID
from sqlalchemy import func, select
from starlette import status

import media_manager.notification.utils
from media_manager.auth.db import User, get_async_session, get_user_db
from media_manager.auth.schemas import UserCreate, UserUpdate
from media_manager.config import MediaManagerConfig

log = logging.getLogger(__name__)

config = MediaManagerConfig().auth
SECRET = config.token_secret
LIFETIME = config.session_lifetime

openid_client: OpenID | None = None
if config.openid_connect.enabled:
    log.info(f"Configured OIDC provider: {config.openid_connect.name}")
    openid_client = OpenID(
        base_scopes=["openid", "email", "profile"],
        client_id=config.openid_connect.client_id,
        client_secret=config.openid_connect.client_secret,
        name=config.openid_connect.name,
        openid_configuration_endpoint=config.openid_connect.configuration_endpoint,
    )


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    verification_token_lifetime_seconds = 86400

    async def validate_password(self,password,user):
        from fastapi_users.exceptions import InvalidPasswordException
        from media_manager.auth.password_policy import validate_password
        try:validate_password(password)
        except ValueError as error:raise InvalidPasswordException(reason=str(error)) from None

    async def on_after_update(self,user,update_dict,request=None):
        if 'email' in update_dict:
            await self.user_db.update(user,{'is_verified':False})
            from media_manager.auth.mail import send_verification
            send_verification(user)

    async def update(self,user_update,user,safe=False,request=None):
        from media_manager.auth.mail import mail_ready
        from fastapi import HTTPException
        if user_update.email and str(user_update.email).lower()!=user.email.lower() and not mail_ready():
            raise HTTPException(503,'Configure SMTP before changing an email address.')
        if user_update.email and str(user_update.email).lower()==user.email.lower():
            user_update=user_update.__class__(**user_update.model_dump(exclude_unset=True,exclude={'email'}))
        return await super().update(user_update,user,safe=safe,request=request)

    async def on_after_register(self,user,request=None):
        # Public registration is handled by the invitation router. Never grant
        # administrator rights merely because an unverified address matches config.
        log.info('Account created: %s',user.id)

    async def on_after_forgot_password(self,user,token,request=None):
        from media_manager.auth.mail import send_link,mail_ready
        if mail_ready() and MediaManagerConfig().auth.email_password_resets:send_link(user.email,token,'reset',getattr(user,'preferred_language',None) or 'de')

    async def on_after_request_verify(self,user,token,request=None):
        from media_manager.auth.mail import send_link,mail_ready
        if mail_ready():send_link(user.email,token,'verify')

    async def oauth_callback(self,oauth_name,access_token,account_id,account_email,expires_at=None,refresh_token=None,request=None,*,associate_by_email=False,is_verified_by_default=False):
        from fastapi import HTTPException
        try:
            existing=await self.user_db.get_by_oauth_account(oauth_name,account_id)
            if existing is None:raise ValueError('No linked account')
        except Exception:raise HTTPException(403,'New accounts require an invitation or administrator provisioning.') from None
        return await super().oauth_callback(oauth_name,access_token,account_id,account_email,expires_at,refresh_token,request,associate_by_email=False,is_verified_by_default=False)

    @override
    async def on_after_reset_password(
        self, user: User, request: Request | None = None
    ) -> None:
        log.info(f"User {user.id} has reset their password.")

    @override
    async def on_after_verify(self, user: User, request: Request | None = None) -> None:
        from media_manager.auth.mail import notify_admins
        notify_admins('Account confirmed','Email confirmed: '+user.email)
        log.info('Account verified: %s',user.id)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager]:
    yield UserManager(user_db)


get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


async def create_default_admin_user() -> None:
    """Create a default admin user if no users exist in the database"""
    try:
        async with get_async_session_context() as session:
            async with get_user_db_context(session) as user_db:
                async with get_user_manager_context(user_db) as user_manager:
                    # Check if any users exist
                    stmt = select(func.count(User.id))
                    result = await session.execute(stmt)
                    user_count = result.scalar()
                    config = MediaManagerConfig()
                    if user_count == 0:
                        log.info(
                            "No users found in database. Creating default admin user..."
                        )

                        # Use the first admin email from config, or default
                        admin_email = (
                            config.auth.admin_emails[0]
                            if config.auth.admin_emails
                            else "admin@example.com"
                        )
                        initial_file = config_file().parent / 'initial-admin.json'
                        initial = json.loads(initial_file.read_text()) if initial_file.exists() else {}
                        admin_email = initial.get('email', admin_email)
                        default_password = initial.get('password') or ('Admin!A1'+__import__('secrets').token_urlsafe(18))
                        if not initial:
                            from media_manager.configuration import atomic_json
                            atomic_json(config_file().parent/'bootstrap-admin.json',{'email':admin_email,'password':default_password})

                        user_create = UserCreate(
                            email=admin_email,
                            password=default_password,
                            is_superuser=True,
                            is_verified=True,
                        )

                        user = await user_manager.create(user_create)
                        log.info("=" * 60)
                        log.info("DEFAULT ADMIN USER CREATED!")
                        log.info(f"    Email: {admin_email}")
                        if initial:
                            initial_file.unlink()
                            code_file = config_file().parent / 'setup-code'
                            code_file.unlink(missing_ok=True)
                            log.info("Use the administrator password set during onboarding.")
                        else:
                            log.info("Use the initial administrator password and change it after login.")
                        log.info(f"    User ID: {user.id}")
                        log.info(
                            "IMPORTANT: Please change this password after first login!"
                        )
                        log.info("=" * 60)

                    else:
                        log.info(
                            f"Found {user_count} existing users. Skipping default user creation."
                        )
    except Exception:
        log.exception("Failed to create default admin user")
        log.info(
            "You can create an admin user manually by registering with an email from the admin_emails list in your config."
        )


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=SECRET, lifetime_seconds=LIFETIME)


# needed because the default CookieTransport does not redirect after login,
# thus the user would be stuck on the OAuth Providers "redirecting" page
class RedirectingCookieTransport(CookieTransport):
    async def get_login_response(self, token: str) -> Response:
        response = RedirectResponse(
            str(MediaManagerConfig().misc.frontend_url) + "web/dashboard",
            status_code=status.HTTP_302_FOUND,
        )
        return self._set_login_cookie(response, token)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
cookie_transport = CookieTransport(
    cookie_max_age=LIFETIME, cookie_samesite="lax", cookie_secure=False
)
openid_cookie_transport = RedirectingCookieTransport(
    cookie_max_age=LIFETIME, cookie_samesite="lax", cookie_secure=False
)

bearer_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
openid_cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=openid_cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [bearer_auth_backend, cookie_auth_backend]
)

current_active_user = fastapi_users.current_user(active=True, verified=True)
current_superuser = fastapi_users.current_user(
    active=True, verified=True, superuser=True
)
