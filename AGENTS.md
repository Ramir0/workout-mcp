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
| Install git hooks | `uv run pre-commit install` |
| Run linter | `uv run ruff check .` |
| Run formatter | `uv run ruff format .` |
| Run type checker | `uv run mypy .` |
| Run tests | `uv run pytest` |
| Run all hooks | `uv run pre-commit run --all-files` |
| Run server | `python main.py` |

## State of the Codebase

- **Early stage**: `main.py` is a stub. The README describes the full intended architecture (REST API, MCP tools, DB schema), but most of it is not yet implemented.
- Dev tooling configured: ruff (lint + format), mypy (strict mode), pytest, pre-commit hooks.
- Config files: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`.

## Architecture (from README)

- **REST API**: `POST /import/csv` to ingest Hevy exports.
- **MCP Tools**: `get_workout_by_date_range`, `get_workout_by_routine`, `get_workout_by_exercise`, `get_workout_count`, `get_min_pr_by_exercise`, `get_max_pr_by_exercise`, `get_last_workout`.
- **DB Schema**: see `README.md` ER diagram. Tables: `routine`, `workout`, `exercise`, `workout_exercise`, `set`.

## Notes for Agents

- Keep `pyproject.toml` as the single source of truth for project metadata and dependencies.
- When implementing, match the schema and tool signatures described in `README.md`.
- Ensure all pre-commit hooks pass before committing (`uv run pre-commit run --all-files`).
