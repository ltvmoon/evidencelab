"""Unit tests for the sliding-session refresh endpoint (POST /auth/refresh)."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

COOKIE_NAME = "evidencelab_auth"


class _FakeStrategy:
    """Minimal JWT strategy stub — writes a deterministic token."""

    async def write_token(self, user) -> str:
        """Return a fixed token regardless of the user."""
        return "fresh-token"


def _build_app(*, authenticated: bool) -> FastAPI:
    """Build a FastAPI app mounting the real auth router.

    Args:
        authenticated: When True, override the auth dependencies so the
            request is treated as an authenticated user.

    Returns:
        FastAPI: The configured application.
    """
    from ui.backend.auth.users import cookie_backend, current_active_user
    from ui.backend.routes import auth as auth_routes

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")

    if authenticated:
        app.dependency_overrides[current_active_user] = lambda: SimpleNamespace(
            id="user-1"
        )
        app.dependency_overrides[cookie_backend.get_strategy] = _FakeStrategy
    return app


@pytest.mark.unit
def test_refresh_when_authenticated_reissues_cookie():
    """An authenticated refresh returns 204 and a fresh auth cookie."""
    client = TestClient(_build_app(authenticated=True))

    resp = client.post("/auth/refresh")

    assert resp.status_code == 204
    set_cookie = resp.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=fresh-token" in set_cookie


@pytest.mark.unit
def test_refresh_when_unauthenticated_returns_401():
    """Refresh without a valid session is rejected (cannot bootstrap)."""
    client = TestClient(_build_app(authenticated=False))

    resp = client.post("/auth/refresh")

    assert resp.status_code == 401
