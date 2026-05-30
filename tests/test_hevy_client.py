from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from workout_mcp.hevy_client import (
    HevyAPIError,
    HevyAuthError,
    HevyClient,
    HevyRateLimitError,
)


@pytest.fixture
def client() -> HevyClient:
    return HevyClient(api_key="test-key")


@pytest.mark.anyio
async def test_get_workout_success(client: HevyClient) -> None:
    mock_response = httpx.Response(200, json={"id": "w1", "title": "Push Day"})
    with patch.object(
        client._client, "request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_workout("w1")
    assert result["id"] == "w1"
    assert result["title"] == "Push Day"


@pytest.mark.anyio
async def test_get_workout_not_found(client: HevyClient) -> None:
    mock_response = httpx.Response(404, json={"error": "not found"})
    with (
        patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response),
        pytest.raises(HevyAPIError, match="404") as exc_info,
    ):
        await client.get_workout("w1")
    assert exc_info.value.status_code == 404
    assert exc_info.value.url is not None
    assert exc_info.value.method == "GET"
    assert exc_info.value.response_text is not None


@pytest.mark.anyio
async def test_get_workout_rate_limit(client: HevyClient) -> None:
    mock_response = httpx.Response(429)
    with (
        patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response),
        pytest.raises(HevyRateLimitError) as exc_info,
    ):
        await client.get_workout("w1")
    assert exc_info.value.status_code == 429
    assert exc_info.value.url is not None


@pytest.mark.anyio
async def test_get_workout_auth_error(client: HevyClient) -> None:
    mock_response = httpx.Response(401)
    with (
        patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response),
        pytest.raises(HevyAuthError) as exc_info,
    ):
        await client.get_workout("w1")
    assert exc_info.value.status_code == 401
    assert exc_info.value.url is not None


@pytest.mark.anyio
async def test_get_workout_events(client: HevyClient) -> None:
    since = datetime(2024, 1, 1, tzinfo=UTC)
    mock_response = httpx.Response(
        200,
        json={"events": [{"type": "updated", "workout": {"id": "w1", "title": "Leg Day"}}]},
    )
    with patch.object(
        client._client, "request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_workout_events(since)
    assert len(result["events"]) == 1


@pytest.mark.anyio
async def test_get_workouts(client: HevyClient) -> None:
    mock_response = httpx.Response(200, json={"workouts": [{"id": "w1", "title": "Push Day"}]})
    with patch.object(
        client._client, "request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_workouts()
    assert len(result["workouts"]) == 1
