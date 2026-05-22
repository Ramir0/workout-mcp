# Workout MCP Server — Agent Guide

Compact reference for AI agents working in this repo.

## Project

- **Goal**: MCP server + REST API for ingesting and querying workout data from Hevy CSV exports.
- **Stack**: Python ≥3.13, `uv` for deps, `mcp[cli]`, `httpx`, `sqlalchemy>=2.0`.
- **Entrypoint**: `main.py` (runs FastAPI via uvicorn on port 8000).
- **Database**: relational (PostgreSQL) with schema: Routine → Workout → Exercise → Set.

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Install git hooks | `uv run pre-commit install` |
| Run linter | `uv run ruff check .` |
| Run formatter | `uv run ruff format .` |
| Run type checker | `uv run mypy .` |
| Run tests | `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest` |
| Run tests with coverage | `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest --cov --cov-report=term-missing --cov-fail-under=90` |
| Run all hooks | `uv run pre-commit run --all-files` |
| Run server | `python main.py` |

## State of the Codebase

- **Current state**: ORM models defined (`workout_mcp/models.py`) with unique constraints for upsert support. Database infrastructure implemented: `workout_mcp/config.py`, `workout_mcp/database.py`, Alembic migrations (`alembic/`). Hevy CSV parser implemented (`workout_mcp/parser.py`) with test fixtures and unit tests. FastAPI REST API implemented (`workout_mcp/api.py`) with `POST /import/csv` endpoint for CSV ingestion with upsert/deduplication. MCP server scaffold implemented (`workout_mcp/mcp_server.py`) with FastMCP instance (stateless HTTP) and DB session helper. MCP server mounted on FastAPI at `/mcp` in `main.py` with lifespan integration. All 7 MCP tools implemented: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_last_workout`, `get_max_pr_by_exercise`, `get_min_pr_by_exercise` with tests (`tests/test_mcp_tools.py`). Docker support added: `Dockerfile`, `.dockerignore`, `docker-compose.prod.yml`. Test infrastructure in place: `tests/conftest.py` (transaction-isolated fixtures + TestClient), `tests/test_models.py`, `tests/test_database.py` (integration tests), `tests/test_parser.py` (parser tests), `tests/test_api.py` (API integration tests including error paths), `tests/test_config.py` (config tests), `tests/test_main.py` (app structure tests), `tests/test_mcp_tools.py` (MCP tool tests including xfail error paths), `tests/fixtures/` (CSV test data). Wave 3 completed. Issue #16 (comprehensive test coverage) completed: 90% coverage threshold enforced in CI, coverage config in pyproject.toml.
- Dev tooling configured: ruff (lint + format), mypy (strict mode), pytest, pre-commit hooks.
- Config files: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `alembic.ini`, `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile`, `.dockerignore`, `.env.example`.

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
- **Test Coverage**: 90% threshold enforced in CI via `pytest-cov`. Run with `uv run pytest --cov --cov-report=term-missing --cov-fail-under=90`.
- **DB Schema**: see `README.md` ER diagram. Tables: `routine`, `workout`, `exercise`, `workout_exercise`, `set`.

## Notes for Agents

- Keep `pyproject.toml` as the single source of truth for project metadata and dependencies.
- When implementing, match the schema and tool signatures described in `README.md`.
- Ensure all pre-commit hooks pass before committing (`uv run pre-commit run --all-files`).
- **Commit freely** when following implementation plans in `docs/plans/` specify exactly when and what to commit.
