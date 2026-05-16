# Workout MCP Server — Agent Guide

Compact reference for AI agents working in this repo.

## Project

- **Goal**: MCP server + REST API for ingesting and querying workout data from Hevy CSV exports.
- **Stack**: Python ≥3.13, `uv` for deps, `mcp[cli]`, `httpx`, `sqlalchemy>=2.0`.
- **Entrypoint**: `main.py` (stub; intended to start the MCP server).
- **Database**: relational (PostgreSQL) with schema: Routine → Workout → Exercise → Set.

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Install git hooks | `uv run pre-commit install` |
| Run linter | `uv run ruff check .` |
| Run formatter | `uv run ruff format .` |
| Run type checker | `uv run mypy .` |
| Run tests | `uv run pytest` |
| Run all hooks | `uv run pre-commit run --all-files` |
| Run server | `python main.py` |

## State of the Codebase

- **Current state**: ORM models defined (`workout_mcp/models.py`) with unit tests (`tests/test_models.py`). Database infrastructure implemented: `workout_mcp/config.py`, `workout_mcp/database.py`, Alembic migrations (`alembic/`). `main.py` is still a stub. The README describes the full intended architecture (REST API, MCP tools, DB schema).
- Dev tooling configured: ruff (lint + format), mypy (strict mode), pytest, pre-commit hooks.
- Config files: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `alembic.ini`, `docker-compose.yml`, `.env.example`.

## Local Development

To start PostgreSQL for local development:

```bash
docker-compose up -d
```

To run migrations:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head
```

To run tests (requires PostgreSQL running):

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest
```

## Architecture (from README)

- **REST API**: `POST /import/csv` to ingest Hevy exports.
- **MCP Tools**: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_min_pr_by_exercise`, `get_max_pr_by_exercise`, `get_last_workout`.
- **DB Schema**: see `README.md` ER diagram. Tables: `routine`, `workout`, `exercise`, `workout_exercise`, `set`.

## Notes for Agents

- Keep `pyproject.toml` as the single source of truth for project metadata and dependencies.
- When implementing, match the schema and tool signatures described in `README.md`.
- Ensure all pre-commit hooks pass before committing (`uv run pre-commit run --all-files`).
- **Commit freely** when following implementation plans in `docs/plans/` specify exactly when and what to commit.
