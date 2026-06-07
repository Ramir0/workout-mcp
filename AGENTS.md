# Workout MCP Server — Agent Guide

Compact reference for AI agents working in this repo.

## Project

- **Goal**: MCP server + REST API for ingesting and querying workout data from Hevy CSV exports.
- **Stack**: Python ≥3.13, `uv` for deps, `mcp[cli]`, `httpx`, `sqlalchemy>=2.0`, `structlog`, `pydantic-settings`.
- **Entrypoints**:
  - `main.py` — REST API server (uvicorn, port 9090)
  - `mcp_server_main.py` — MCP server (uvicorn, port 9091)
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
| Run REST API | `python main.py` |
| Run MCP Server | `python mcp_server_main.py` |
| Import CSV | `curl -X POST http://localhost:9090/import/csv -H "Content-Type: text/csv" --data-binary @file.csv` |
| Sync Hevy | `curl -X POST http://localhost:9090/sync/hevy` |

## State of the Codebase

- **Current state**: ORM models defined (`workout_mcp/models.py`) with unique constraints for upsert support. `workout_exercise` has `UniqueConstraint("workout_id", "exercise_id", "exercise_index")` so the same exercise can appear at multiple positions in a routine (e.g., a warm-up set and working sets of the same lift). Database infrastructure implemented: `workout_mcp/config.py` (pydantic-settings), `workout_mcp/database.py`, Alembic migrations (`alembic/`). Hevy CSV parser implemented (`workout_mcp/parser.py`) — tracks per-exercise occurrence index in first-appearance order so duplicate exercise names within one workout become distinct `ParsedExercise` entries with unique `exercise_index` values. FastAPI REST API implemented (`workout_mcp/api.py`) with `POST /import/csv` endpoint for CSV ingestion and `POST /sync/hevy` for on-demand Hevy API sync (incremental mode). Hevy API integration: `workout_mcp/hevy_client.py` (async httpx wrapper), `workout_mcp/hevy_mapper.py` (JSON → ORM), `workout_mcp/sync.py` (incremental events polling), `workout_mcp/sync_service.py` (DB upsert). Webhook endpoint `POST /webhooks/hevy` for real-time Hevy notifications (background task). No periodic auto-sync — sync is always on-demand or webhook-triggered. Upsert logic looks up `WorkoutExercise` by the full `(workout_id, exercise_id, exercise_index)` key; on routine re-import the existing `WorkoutExercise` set is purged (ORM cascade drops the child `Set` rows) before re-inserting. Structured exception handlers (422/409/500) and request logging middleware with X-Request-ID. Structured logging configured (`workout_mcp/logging.py`) with structlog (JSON/console renderers). MCP server shelf implemented (`workout_mcp/mcp_server.py`) with FastMCP instance (stateless HTTP) and DB session helper. MCP server entry point (`mcp_server_main.py`) runs as a standalone uvicorn process on port 9091 with lifespan integration. All 7 MCP tools implemented: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_last_workout`, `get_max_pr_by_exercise`, `get_min_pr_by_exercise` with tests (`tests/test_mcp_tools.py`). Docker support added: `Dockerfile`, `.dockerignore`, `docker-compose.prod.yml`. Test infrastructure in place: `tests/conftest.py` (transaction-isolated fixtures + TestClient), `tests/test_models.py`, `tests/test_database.py` (integration tests), `tests/test_parser.py` (parser tests), `tests/test_api.py` (API integration tests including error paths), `tests/test_config.py` (config tests), `tests/test_logging.py` (logging tests), `tests/test_main.py` (app structure tests), `tests/test_mcp_tools.py` (MCP tool tests including xfail error paths), `tests/fixtures/` (CSV test data including `duplicate_exercise.csv`). 90% coverage threshold enforced in CI; structlog, pydantic-settings, exception handlers, request logging middleware, MCP tool error handling all in place.
- Dev tooling configured: ruff (lint + format), mypy (strict mode), pytest, pre-commit hooks.
- Config files: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `alembic.ini`, `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile`, `.dockerignore`, `.env.example`.
- Application modules: `workout_mcp/config.py` (pydantic-settings), `workout_mcp/database.py`, `workout_mcp/logging.py` (structlog), `workout_mcp/api.py` (exception handlers + middleware, replace-on-reimport for `WorkoutExercise`), `workout_mcp/mcp_server.py` (error handling), `workout_mcp/parser.py` (occurrence-aware), `main.py`, `mcp_server_main.py`.

## Local Development

1. Copy the example environment file and adjust values for your machine:

```bash
cp .env.example .env
```

2. Start PostgreSQL for local development:

```bash
docker-compose up -d
```

3. Run migrations:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head
```

4. Run tests (requires PostgreSQL running):

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest
```

## Architecture (from README)

- **REST API**: `POST /import/csv` to ingest Hevy exports; `POST /sync/hevy` for on-demand Hevy API sync; `POST /webhooks/hevy` for real-time webhook notifications.
- **MCP Tools**: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_min_pr_by_exercise`, `get_max_pr_by_exercise`, `get_last_workout`.
- **Test Coverage**: 90% threshold enforced in CI via `pytest-cov`. Run with `uv run pytest --cov --cov-report=term-missing --cov-fail-under=90`.
- **DB Schema**: see `README.md` ER diagram. Tables: `routine`, `workout`, `exercise`, `workout_exercise`, `set`. The `workout_exercise` unique key is `(workout_id, exercise_id, exercise_index)` so a routine can legitimately include the same exercise at multiple positions; the parser emits a distinct `ParsedExercise` per occurrence and `/import/csv` upserts each by the full three-column key, purging stale `WorkoutExercise` rows on re-import so reorders and additions produce the exact new layout.

## Notes for Agents

- Keep `pyproject.toml` as the single source of truth for project metadata and dependencies.
- When implementing, match the schema and tool signatures described in `README.md`.
- Ensure all pre-commit hooks pass before committing (`uv run pre-commit run --all-files`).
- **Commit freely** when following implementation plans in `docs/plans/` specify exactly when and what to commit.
- When adding new entry points, expose both `APP_PORT` and `MCP_PORT` in Dockerfile and document in README.
