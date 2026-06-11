"""Unit tests for the session-timing fields on GET /config/auth-status."""

import os
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_auth_status_exposes_session_timing_overrides():
    """auth-status returns the configured token lifetime and idle timeout."""
    from ui.backend.routes import config as config_mod

    env = {"AUTH_TOKEN_LIFETIME": "1800", "AUTH_IDLE_TIMEOUT": "2400"}
    with patch.dict(os.environ, env, clear=False):
        result = config_mod.get_auth_status()

    assert result["token_lifetime_seconds"] == 1800
    assert result["session_idle_timeout_seconds"] == 2400


@pytest.mark.unit
def test_auth_status_session_timing_defaults():
    """Session timing defaults to 3600 seconds when env is unset."""
    from ui.backend.routes import config as config_mod

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AUTH_TOKEN_LIFETIME", None)
        os.environ.pop("AUTH_IDLE_TIMEOUT", None)
        result = config_mod.get_auth_status()

    assert result["token_lifetime_seconds"] == 3600
    assert result["session_idle_timeout_seconds"] == 3600
