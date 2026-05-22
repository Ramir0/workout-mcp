"""Tests for main.py — REST API entry point."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_has_correct_title() -> None:
    """FastAPI app has the expected title."""
    from workout_mcp.api import app

    assert app.title == "Workout MCP Server"


def test_health_endpoint() -> None:
    """FastAPI app is accessible."""
    from workout_mcp.api import app

    client = TestClient(app)
    response = client.post("/import/csv")
    assert response.status_code == 422
