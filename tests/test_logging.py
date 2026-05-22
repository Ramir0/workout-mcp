"""Tests for workout_mcp.logging module."""

from __future__ import annotations

from unittest.mock import patch

from workout_mcp.logging import get_logger, setup_logging


def test_setup_logging_console_format() -> None:
    """setup_logging configures structlog in console mode."""
    with patch("workout_mcp.logging.settings") as mock_settings:
        mock_settings.log_level = "DEBUG"
        mock_settings.log_format = "console"
        setup_logging()


def test_setup_logging_json_format() -> None:
    """setup_logging configures structlog in JSON mode."""
    with patch("workout_mcp.logging.settings") as mock_settings:
        mock_settings.log_level = "WARNING"
        mock_settings.log_format = "json"
        setup_logging()


def test_setup_logging_invalid_log_level() -> None:
    """setup_logging handles invalid log level gracefully."""
    with patch("workout_mcp.logging.settings") as mock_settings:
        mock_settings.log_level = "INVALID"
        mock_settings.log_format = "console"
        setup_logging()


def test_get_logger_returns_bound_logger() -> None:
    """get_logger returns a usable logger after setup."""
    with patch("workout_mcp.logging.settings") as mock_settings:
        mock_settings.log_level = "INFO"
        mock_settings.log_format = "console"
        setup_logging()

    logger = get_logger("test_module")
    assert logger is not None
    logger.info("test_message", key="value")


def test_get_logger_can_log() -> None:
    """get_logger returns a usable logger even before explicit setup."""
    logger = get_logger("test_module")
    assert logger is not None
    logger.info("test_lazy_message", key="value")
