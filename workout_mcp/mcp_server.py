"""MCP server with workout query tools."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from workout_mcp.database import SessionLocal

mcp = FastMCP(
    "WorkoutServer",
    stateless_http=True,
    json_response=True,
)


@contextmanager
def get_db_session() -> Generator[Session]:
    """Yield a database session, closing it on exit."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
