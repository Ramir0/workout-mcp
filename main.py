"""Entry point for the Workout MCP Server."""

import uvicorn

from workout_mcp.api import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
