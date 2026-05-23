"""Async HTTP client for the Hevy API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import httpx

from workout_mcp.config import settings
from workout_mcp.logging import get_logger

logger = get_logger(__name__)


class HevyAPIError(Exception):
    """Base exception for Hevy API errors."""

    pass


class HevyRateLimitError(HevyAPIError):
    """Raised when Hevy returns HTTP 429."""

    pass


class HevyAuthError(HevyAPIError):
    """Raised when Hevy returns HTTP 401 or 403."""

    pass


class HevyClient:
    """Thin async wrapper around the Hevy REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.hevy_api_key or ""
        self.base_url = str(base_url or settings.hevy_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"api-key": self.api_key},
            timeout=30.0,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = await self._client.request(method, url, **kwargs)

        if response.status_code == 429:
            raise HevyRateLimitError("Hevy API rate limit exceeded")
        if response.status_code in (401, 403):
            raise HevyAuthError(f"Hevy API auth error: {response.status_code}")
        if response.status_code >= 400:
            raise HevyAPIError(f"Hevy API error {response.status_code}: {response.text}")

        return cast(dict[str, Any], response.json())

    async def get_workout(self, workout_id: str) -> dict[str, Any]:
        """Fetch a single workout by ID."""
        return await self._request("GET", f"/v1/workouts/{workout_id}")

    async def get_workout_events(
        self, since: datetime, page: int = 1, page_size: int = 10
    ) -> dict[str, Any]:
        """Fetch paginated workout events (updates and deletions) since a timestamp."""
        since_iso = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "since": since_iso,
            "page": page,
            "pageSize": page_size,
        }
        return await self._request("GET", "/v1/workouts/events", params=params)

    async def get_workouts(self, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """Fetch paginated list of all workouts."""
        params = {"page": page, "pageSize": page_size}
        return await self._request("GET", "/v1/workouts", params=params)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HevyClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
