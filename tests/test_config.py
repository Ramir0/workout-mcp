"""Tests for workout_mcp.config module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_settings_loads_defaults() -> None:
    """Settings loads default values when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        from workout_mcp.config import Settings  # type: ignore[attr-defined]

        settings = Settings()  # type: ignore[call-arg]
        assert settings.database_url == "postgresql://postgres:postgres@localhost:5432/workout_mcp"
        assert (
            settings.test_database_url
            == "postgresql://postgres:postgres@localhost:5432/workout_mcp_test"
        )
        assert settings.app_port == 8000
        assert settings.log_level == "INFO"
        assert settings.log_format == "console"


def test_settings_env_override() -> None:
    """Settings values can be overridden via environment variables."""
    env = {
        "DATABASE_URL": "postgresql://custom:custom@localhost:5432/custom_db",
        "APP_PORT": "9000",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=True):
        from workout_mcp.config import Settings  # type: ignore[attr-defined]

        settings = Settings()  # type: ignore[call-arg]
        assert settings.database_url == "postgresql://custom:custom@localhost:5432/custom_db"
        assert settings.app_port == 9000
        assert settings.log_level == "DEBUG"


def test_settings_invalid_port() -> None:
    """Settings raises ValidationError for invalid port."""
    with patch.dict(os.environ, {"APP_PORT": "not_a_number"}, clear=True):
        from workout_mcp.config import Settings  # type: ignore[attr-defined]

        with pytest.raises(Exception):  # noqa: B017  # ValidationError
            Settings()  # type: ignore[call-arg]
