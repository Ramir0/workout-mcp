"""Entry point for the Workout MCP Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn

from workout_mcp.config import settings
from workout_mcp.logging import setup_logging
from workout_mcp.mcp_server import mcp


# Wrap MCP session manager as the app lifespan.
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    async with mcp.session_manager.run():
        yield


app = mcp.streamable_http_app()
app.router.lifespan_context = lifespan


def main() -> None:
    setup_logging()
    uvicorn.run(app, host="0.0.0.0", port=settings.mcp_port)


if __name__ == "__main__":
    main()
