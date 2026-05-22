"""Tests for main.py — app mounting and lifespan."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_has_correct_title() -> None:
    """FastAPI app has the expected title."""
    from workout_mcp.api import app

    assert app.title == "Workout MCP Server"


def test_mcp_server_is_mounted() -> None:
    """MCP server is mounted at /mcp."""
    __import__("main")  # triggers MCP mount on app

    from workout_mcp.api import app

    mcp_routes = [r for r in app.routes if hasattr(r, "path") and r.path == "/mcp"]
    assert len(mcp_routes) > 0


def test_health_endpoint() -> None:
    """FastAPI app is accessible."""
    from workout_mcp.api import app

    client = TestClient(app)
    response = client.post("/import/csv")
    assert response.status_code == 422
