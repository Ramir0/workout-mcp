"""Tests for mcp_server_main.py — standalone MCP server entry point."""

from __future__ import annotations


def test_mcp_app_is_importable() -> None:
    """MCP server entry point is importable and has app."""
    import mcp_server_main

    assert hasattr(mcp_server_main, "app")


def test_mcp_app_has_lifespan() -> None:
    """MCP server app has a lifespan context configured."""
    import mcp_server_main

    assert mcp_server_main.app.router.lifespan_context is not None
