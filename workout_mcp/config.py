"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/workout_mcp"
    test_database_url: str = "postgresql://postgres:postgres@localhost:5432/workout_mcp_test"
    app_port: int = 9090
    mcp_port: int = 9091
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

# Backward-compatible exports for existing code
DATABASE_URL: str = settings.database_url
TEST_DATABASE_URL: str = settings.test_database_url
