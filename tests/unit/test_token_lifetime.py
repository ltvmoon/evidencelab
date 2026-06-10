"""Unit tests for the env-configurable access-token lifetime."""

import importlib
import os
from unittest.mock import patch

import pytest

# A valid (>=32 char) secret so reloading users.py does not fall back to an
# ephemeral random secret (which only logs a warning, but keeps output clean).
_TEST_SECRET = "x" * 48  # pragma: allowlist secret


@pytest.mark.unit
def test_token_lifetime_defaults_to_one_hour():
    """Without AUTH_TOKEN_LIFETIME set, the lifetime is 3600 seconds."""
    with patch.dict(os.environ, {"AUTH_SECRET_KEY": _TEST_SECRET}, clear=False):
        # patch.dict restores the original environment on exit, so this
        # deletion is reverted afterwards.
        os.environ.pop("AUTH_TOKEN_LIFETIME", None)
        import ui.backend.auth.users as users

        importlib.reload(users)
        try:
            assert users.TOKEN_LIFETIME_SECONDS == 3600
        finally:
            importlib.reload(users)


@pytest.mark.unit
def test_token_lifetime_reads_env_override():
    """AUTH_TOKEN_LIFETIME drives the JWT strategy and cookie max-age."""
    env = {"AUTH_SECRET_KEY": _TEST_SECRET, "AUTH_TOKEN_LIFETIME": "7200"}
    with patch.dict(os.environ, env, clear=False):
        import ui.backend.auth.users as users

        importlib.reload(users)
        try:
            assert users.TOKEN_LIFETIME_SECONDS == 7200
            assert users.get_jwt_strategy().lifetime_seconds == 7200
            assert users.cookie_transport.cookie_max_age == 7200
        finally:
            # Restore module state for other tests in the session.
            importlib.reload(users)
