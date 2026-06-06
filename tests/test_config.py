"""Tests for workout_mcp.config module."""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch

import workout_mcp.config


def test_config_exports_database_url() -> None:
    """Config module exports DATABASE_URL as a string."""
    assert isinstance(workout_mcp.config.DATABASE_URL, str)
    assert len(workout_mcp.config.DATABASE_URL) > 0


def test_config_exports_test_database_url() -> None:
    """Config module exports TEST_DATABASE_URL as a string."""
    assert isinstance(workout_mcp.config.TEST_DATABASE_URL, str)
    assert len(workout_mcp.config.TEST_DATABASE_URL) > 0


def test_database_url_env_override() -> None:
    """DATABASE_URL reads from environment variable."""
    original = workout_mcp.config.DATABASE_URL
    try:
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql://custom:custom@localhost:5432/custom_db"}
        ):
            importlib.reload(workout_mcp.config)
            assert (
                workout_mcp.config.DATABASE_URL
                == "postgresql://custom:custom@localhost:5432/custom_db"
            )
    finally:
        importlib.reload(workout_mcp.config)
        assert original == workout_mcp.config.DATABASE_URL


def test_test_database_url_env_override() -> None:
    """TEST_DATABASE_URL reads from environment variable."""
    original = workout_mcp.config.TEST_DATABASE_URL
    try:
        with patch.dict(
            os.environ, {"TEST_DATABASE_URL": "postgresql://test:test@localhost:5432/test_db"}
        ):
            importlib.reload(workout_mcp.config)
            assert (
                workout_mcp.config.TEST_DATABASE_URL
                == "postgresql://test:test@localhost:5432/test_db"
            )
    finally:
        importlib.reload(workout_mcp.config)
        assert original == workout_mcp.config.TEST_DATABASE_URL


def test_mcp_port_setting() -> None:
    """Settings includes mcp_port with default 9091."""
    from workout_mcp.config import Settings

    settings = Settings()
    assert settings.mcp_port == 9091


def test_hevy_config_fields() -> None:
    """Settings includes Hevy API configuration fields."""
    from workout_mcp.config import Settings

    with patch.dict(
        os.environ,
        {
            "HEVY_API_KEY": "test-api-key-123",
            "HEVY_BASE_URL": "https://api.hevyapp.com",
            "HEVY_SYNC_INTERVAL_MINUTES": "60",
        },
    ):
        settings = Settings()
        assert settings.hevy_api_key == "test-api-key-123"
        assert settings.hevy_base_url == "https://api.hevyapp.com"
        assert settings.hevy_sync_interval_minutes == 60
