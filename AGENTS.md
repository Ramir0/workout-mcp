# Workout MCP Server — Agent Guide

Compact reference for AI agents working in this repo.

## Project

- **Goal**: MCP server + REST API for ingesting and querying workout data from Hevy CSV exports.
- **Stack**: Python ≥3.13, `uv` for deps, `mcp[cli]`, `httpx`.
- **Entrypoint**: `main.py` (stub; intended to start the MCP server).
- **Database**: relational (PostgreSQL) with schema: Routine → Workout → Exercise → Set.

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run server | `python main.py` |
| Import CSV (while server runs) | `curl -X POST http://localhost:8000/import/csv -F "file=@hevy_export.csv"` |

## State of the Codebase

- **Early stage**: `main.py` is a stub. The README describes the full intended architecture (REST API, MCP tools, DB schema), but most of it is not yet implemented.
- No tests, linters, formatters, or CI configured yet.
- `pyproject.toml` and `uv.lock` are the only config files.

## Architecture (from README)

- **REST API**: `POST /import/csv` to ingest Hevy exports.
- **MCP Tools**: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_min_pr_by_exercise`, `get_max_pr_by_exercise`, `get_last_workout`.
- **DB Schema**: see `README.md` ER diagram. Tables: `routine`, `workout`, `exercise`, `workout_exercise`, `set`.

## Notes for Agents

- Prefer adding tests and tooling (pytest, ruff, mypy) as the project grows.
- Keep `pyproject.toml` as the single source of truth for project metadata and dependencies.
- When implementing, match the schema and tool signatures described in `README.md`.
