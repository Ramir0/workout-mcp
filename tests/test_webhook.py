from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_webhook_returns_200(client: TestClient) -> None:
    with (
        patch("workout_mcp.api.settings.hevy_api_key", "test-key"),
        patch("workout_mcp.api.HevyClient.get_workout", return_value={}),
        patch("workout_mcp.api.upsert_hevy_workout") as mock_upsert,
    ):
        response = client.post("/webhooks/hevy", json={"workoutId": "test-id-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_upsert.assert_called_once()


def test_webhook_without_api_key_returns_503(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.hevy_api_key", None):
        response = client.post("/webhooks/hevy", json={"workoutId": "test-id-123"})
    assert response.status_code == 503
    assert "Hevy API not configured" in response.json()["detail"]


def test_webhook_with_valid_api_key_returns_200(client: TestClient) -> None:
    with (
        patch("workout_mcp.api.settings.hevy_api_key", "test-key"),
        patch("workout_mcp.api.settings.rest_api_key", "test-secret"),
        patch("workout_mcp.api.HevyClient.get_workout", return_value={}),
        patch("workout_mcp.api.upsert_hevy_workout") as mock_upsert,
    ):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
            headers={"X-API-Key": "test-secret"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_upsert.assert_called_once()


def test_webhook_invalid_api_key_returns_400(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.rest_api_key", "secret"):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
            headers={"X-API-Key": "invalid"},
        )
    assert response.status_code == 400
    assert "Invalid API key" in response.json()["detail"]


def test_webhook_missing_api_key_header_returns_400(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.rest_api_key", "secret"):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
        )
    assert response.status_code == 400
    assert "Invalid API key" in response.json()["detail"]
