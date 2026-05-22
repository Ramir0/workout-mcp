"""Entry point for the Workout REST API Server."""

from __future__ import annotations

import uvicorn

from workout_mcp.api import app
from workout_mcp.config import settings
from workout_mcp.logging import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)


if __name__ == "__main__":
    main()
