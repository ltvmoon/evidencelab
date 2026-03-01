"""fastapi-users configuration: UserManager, auth backends, dependency factories."""

import logging
import os
import secrets
import uuid
from typing import AsyncGenerator, Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users import exceptions as fu_exceptions
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from ui.backend.auth.db import get_async_session
from ui.backend.auth.email import send_email
from ui.backend.auth.models import OAuthAccount, User
from ui.backend.services.permissions import add_user_to_default_group

logger = logging.getLogger(__name__)

_INSECURE_DEFAULTS = frozenset(
    {
        "CHANGE-ME-IN-PRODUCTION",
        "changeme-generate-a-real-secret",
        "changeme",
        "secret",
        "",
    }
)

AUTH_SECRET = os.environ.get("AUTH_SECRET_KEY", "")
if AUTH_SECRET in _INSECURE_DEFAULTS or len(AUTH_SECRET) < 32:
    _generated = secrets.token_hex(32)
    logger.critical(
        "AUTH_SECRET_KEY is missing or insecure (len=%d). "
        "Set AUTH_SECRET_KEY to a random 32+ character string "
        "(e.g. `openssl rand -hex 32`). "
        "A random ephemeral secret has been generated for this process — "
        "tokens will NOT survive restarts.",
        len(AUTH_SECRET),
    )
    AUTH_SECRET = _generated

TOKEN_LIFETIME_SECONDS = 3600  # 1 hour (short-lived; refresh via cookie)

# Registration controls — restrict who can sign up.
# Comma-separated list of allowed email domains (e.g. "example.com,corp.org").
# Empty string means open registration (anyone can register).
_ALLOWED_DOMAINS_RAW = os.environ.get("AUTH_ALLOWED_EMAIL_DOMAINS", "")
ALLOWED_EMAIL_DOMAINS: frozenset[str] = frozenset(
    d.strip().lower() for d in _ALLOWED_DOMAINS_RAW.split(",") if d.strip()
)

# Minimum password length enforced at the backend (defence-in-depth).
MIN_PASSWORD_LENGTH = int(os.environ.get("AUTH_MIN_PASSWORD_LENGTH", "8"))


# ---------------------------------------------------------------------------
# User database adapter
# ---------------------------------------------------------------------------


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> SQLAlchemyUserDatabase:
    """Yield a fastapi-users SQLAlchemy database adapter."""
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


# ---------------------------------------------------------------------------
# UserManager — customises registration, verification, etc.
# ---------------------------------------------------------------------------


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Custom user manager with email verification and password reset."""

    reset_password_token_secret = AUTH_SECRET
    verification_token_secret = AUTH_SECRET

    async def validate_password(
        self, password: str, user: User  # type: ignore[override]
    ) -> None:
        """Enforce password complexity and email domain restrictions.

        Raises:
            InvalidPasswordException: If validation fails.
        """
        if len(password) < MIN_PASSWORD_LENGTH:
            raise fu_exceptions.InvalidPasswordException(
                reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        if not any(c.isdigit() for c in password):
            raise fu_exceptions.InvalidPasswordException(
                reason="Password must contain at least one digit."
            )
        if not any(c.isalpha() for c in password):
            raise fu_exceptions.InvalidPasswordException(
                reason="Password must contain at least one letter."
            )

        # Domain whitelist check (only on creation, not update)
        if ALLOWED_EMAIL_DOMAINS and hasattr(user, "email"):
            domain = user.email.rsplit("@", 1)[-1].lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                raise fu_exceptions.InvalidPasswordException(
                    reason="Registration is restricted to approved email domains."
                )

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Add user to default group and send verification email."""
        # Add to default group so new users have baseline access
        async for session in get_async_session():
            await add_user_to_default_group(session, user.id)
        await self.request_verify(user, request)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Send the verification token by email."""
        base_url = os.environ.get("APP_BASE_URL", "http://localhost:3000")
        verify_url = f"{base_url}?verify={token}"
        await send_email(
            to=user.email,
            subject="Verify your Evidence Lab account",
            body_html=(
                f"<p>Welcome to Evidence Lab!</p>"
                f'<p>Please <a href="{verify_url}">click here to verify your email</a>.</p>'
                f"<p>Or paste this link in your browser: {verify_url}</p>"
            ),
        )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Send a password reset link by email."""
        base_url = os.environ.get("APP_BASE_URL", "http://localhost:3000")
        reset_url = f"{base_url}?reset-password={token}"
        await send_email(
            to=user.email,
            subject="Reset your Evidence Lab password",
            body_html=(
                f"<p>You requested a password reset.</p>"
                f'<p><a href="{reset_url}">Click here to reset your password</a>.</p>'
                f"<p>Or paste this link in your browser: {reset_url}</p>"
                f"<p>If you didn't request this, ignore this email.</p>"
            ),
        )


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """Dependency that yields a UserManager instance."""
    yield UserManager(user_db)


# ---------------------------------------------------------------------------
# Authentication backends (JWT via Bearer header + cookie)
# ---------------------------------------------------------------------------


def get_jwt_strategy() -> JWTStrategy:
    """Create a JWT strategy with the configured secret."""
    return JWTStrategy(secret=AUTH_SECRET, lifetime_seconds=TOKEN_LIFETIME_SECONDS)


bearer_transport = BearerTransport(tokenUrl="auth/login")
cookie_transport = CookieTransport(
    cookie_max_age=TOKEN_LIFETIME_SECONDS,
    cookie_name="evidencelab_auth",
    cookie_httponly=True,
    cookie_secure=os.environ.get("AUTH_COOKIE_SECURE", "true").lower() != "false",
    cookie_samesite="lax",
)

bearer_backend = AuthenticationBackend(
    name="jwt-bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

cookie_backend = AuthenticationBackend(
    name="jwt-cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# ---------------------------------------------------------------------------
# FastAPIUsers instance — provides router factories and current_user deps
# ---------------------------------------------------------------------------

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [bearer_backend, cookie_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
