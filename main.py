"""Entry point for the Workout MCP Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from starlette.routing import Mount

from workout_mcp.api import app
from workout_mcp.mcp_server import mcp

# Configure MCP to serve at the mount point root (no nested /mcp path).
# Must be "/" (not "") — Starlette's Route constructor asserts path.startswith("/").
mcp.settings.streamable_http_path = "/"

# Mount MCP server on FastAPI at /mcp.
# NOTE: streamable_http_app() must be called before the lifespan runs —
# it initializes the session_manager that the lifespan depends on.
app.router.routes.append(Mount("/mcp", app=mcp.streamable_http_app()))


# Wrap MCP session manager as the app lifespan.
# If FastAPI ever needs its own lifespan, use combine_lifespans from
# mcp.server.fastmcp.utilities.lifespan to merge both.
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    async with mcp.session_manager.run():
        yield


app.router.lifespan_context = lifespan


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
