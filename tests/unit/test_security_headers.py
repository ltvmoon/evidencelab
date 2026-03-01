"""Unit tests for security response headers middleware."""

from unittest.mock import patch

import httpx
import pytest

from ui.backend.auth.security_headers import SecurityHeadersMiddleware


def _make_app():
    """Create a minimal FastAPI app with SecurityHeadersMiddleware."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/submit")
    async def submit_endpoint():
        return {"status": "created"}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


def _client(app):
    """Create an httpx.AsyncClient for testing the ASGI app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestSecurityHeaders:
    """Verify all required security headers are present on responses."""

    @pytest.mark.asyncio
    async def test_x_content_type_options(self):
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options(self):
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/test")
        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_x_xss_protection_disabled(self):
        """Modern browsers should use CSP; legacy XSS filter is disabled."""
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/test")
        assert response.headers["X-XSS-Protection"] == "0"

    @pytest.mark.asyncio
    async def test_referrer_policy(self):
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/test")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_permissions_policy(self):
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/test")
        assert "camera=()" in response.headers["Permissions-Policy"]
        assert "microphone=()" in response.headers["Permissions-Policy"]
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    @pytest.mark.asyncio
    async def test_headers_on_post_response(self):
        """Security headers should appear on all responses, not just GET."""
        app = _make_app()
        async with _client(app) as client:
            response = await client.post("/submit")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_headers_on_404_response(self):
        """Security headers should appear even on error responses."""
        app = _make_app()
        async with _client(app) as client:
            response = await client.get("/nonexistent")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


class TestHSTSHeader:
    """Test Strict-Transport-Security header (conditional on HTTPS config)."""

    @pytest.mark.asyncio
    async def test_hsts_present_when_cookie_secure_true(self):
        """HSTS should be set when AUTH_COOKIE_SECURE=true (production)."""
        with patch(
            "ui.backend.auth.security_headers._HSTS_VALUE",
            "max-age=31536000; includeSubDomains",
        ):
            app = _make_app()
            async with _client(app) as client:
                response = await client.get("/test")
            assert "Strict-Transport-Security" in response.headers
            assert "max-age=" in response.headers["Strict-Transport-Security"]

    @pytest.mark.asyncio
    async def test_hsts_absent_when_cookie_secure_false(self):
        """HSTS should NOT be set when running in development (HTTP)."""
        with patch("ui.backend.auth.security_headers._HSTS_VALUE", ""):
            app = _make_app()
            async with _client(app) as client:
                response = await client.get("/test")
            assert "Strict-Transport-Security" not in response.headers
            # Other headers should still be present
            assert response.headers["X-Content-Type-Options"] == "nosniff"
