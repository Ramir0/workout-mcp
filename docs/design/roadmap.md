# Roadmap — Workout MCP Server

## Project Context

- **Current state**: `main.py` is a stub (`print("Hello from workout-mcp!")`)
- **Dependencies**: `mcp[cli]>=1.27.1`, `httpx>=0.28.1`
- **Target**: Full MCP server + REST API for ingesting and querying workout data from Hevy CSV exports
- **Stack decisions**:
  - FastAPI + sync SQLAlchemy 2.0
  - Alembic for migrations
  - PostgreSQL for all environments
  - Full dev tooling from day one (pytest, ruff, mypy, pre-commit)

## Architecture Overview

```
┌──────────────────┐
│  AI Agent/Client │ (MCP Protocol)
└────────┬─────────┘
         │
┌────────▼──────────────────────────────────────┐
│        Workout MCP Server                     │
│  ┌──────────────┐    ┌─────────────────────┐  │
│  │ MCP Tools    │    │ REST API            │  │
│  │ (7 tools)    │    │ POST /import/csv    │  │
│  └──────────────┘    └─────────────────────┘  │
│  ┌──────────────────────────────────────────┐ │
│  │ PostgreSQL (Routine→Workout→Exercise→Set)│ │
│  └──────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

## Issue Breakdown

---

### Wave 1: Infrastructure & Foundation

#### Issue #1 — Set up development tooling
**Priority**: P0 — Blocks all other issues

- Add `pytest`, `ruff`, `mypy`, `pytest-cov`, `pre-commit` to dev dependencies
- Configure `ruff` rules (isort, pyupgrade, flake8-equivalent)
- Configure `mypy` with strict mode
- Add pre-commit hooks for formatting, linting, and type checking
- Create initial test directory structure (`tests/`, `tests/conftest.py`)
- Add `pytest.ini` or `pyproject.toml` pytest config

**Acceptance Criteria**:
- `pytest` runs and passes (even if zero tests)
- `ruff check .` passes
- `mypy .` passes
- `pre-commit run --all-files` passes

---

#### Issue #2 — Set up GitHub Actions CI pipeline
**Priority**: P0 — Blocks merge safety

- Add `.github/workflows/ci.yml`
- Jobs: lint (`ruff`), type-check (`mypy`), test (`pytest --cov`)
- Cache `uv` dependencies between runs
- Trigger on PRs and pushes to `main`

**Acceptance Criteria**:
- CI passes on an empty project
- All three jobs run on every PR
- Dependency caching works

---

#### Issue #3 — Define SQLAlchemy ORM models
**Priority**: P0 — Blocks all data features

Implement all 5 tables from the README ER diagram:

```python
class Routine(Base): ...
class Workout(Base): ...
class Exercise(Base): ...
class WorkoutExercise(Base): ...
class Set(Base): ...
```

- Include `relationship()` definitions with proper backrefs
- Foreign key constraints and indexes on foreign keys
- `__repr__` methods
- Full type annotations
- Use `Mapped[]` annotations (SQLAlchemy 2.0 style)

**Acceptance Criteria**:
- All 5 models are importable from a central module
- Relationships are bidirectional and type-safe
- `mypy` passes on the models file

---

#### Issue #4 — Set up database configuration and Alembic migrations
**Priority**: P0 — Blocks persistence

- Add `psycopg2-binary` dependency
- Create database configuration module with:
  - SQLAlchemy `create_engine()` with connection pooling
  - `sessionmaker()` factory
  - Settings via environment variables (`DATABASE_URL`, etc.)
  - Sensible defaults for local development
- Initialize Alembic:
  - Configure `alembic/env.py` with the models metadata
  - Set up `alembic.ini`
- Create initial migration for Issue #3 models

**Acceptance Criteria**:
- `alembic upgrade head` creates all 5 tables in PostgreSQL
- `alembic downgrade -1` removes all tables
- Environment variables configure the connection string
- `mypy` passes on DB config code

---

#### Issue #5 — Create test infrastructure
**Priority**: P0 — Blocks reliable testing

- Add pytest fixtures:
  - `db_engine`: Creates a test database engine
  - `db_session`: Yields a session with transaction rollback isolation
  - `sample_routine`, `sample_workout`, etc.: Factory-like fixtures for seeding data
- Configure test database settings (separate DB name or schema)
- Add a minimal integration test: create a `Routine` via ORM and assert round-trip
- Add test utilities/helpers as needed

**Acceptance Criteria**:
- `pytest` runs with isolated transactions (no test pollution)
- At least one integration test passes, verifying DB round-trip
- Fixtures are reusable and well-documented

---

### Wave 2: Data Ingestion

#### Issue #6 — Implement Hevy CSV parser
**Priority**: P1 — First user-facing feature

- Research/document Hevy CSV export format. Expected columns:
  - `workout_title`, `start_time`, `end_time`
  - `exercise_title`, `set_order`, `weight_kg` (or `weight_lbs`), `reps`, `rpe`
- Implement a parser module that:
  - Reads CSV from file-like object or path
  - Normalizes rows into a nested structure: Routine → Workout → Exercise → Set
  - Validates required fields and types
  - Rejects malformed rows with descriptive error messages
  - Handles date/time parsing (ISO 8601 or Hevy-specific format)
- Edge cases to handle:
  - Empty CSV
  - Missing required columns
  - Malformed dates
  - Negative/zero weight or reps
  - Mixed units (kg/lbs) — normalize to kg or store as-is with unit flag

**Acceptance Criteria**:
- Parser correctly processes a valid sample CSV
- Unit tests cover all edge cases above
- `mypy` passes on parser code

---

#### Issue #7 — Implement REST API endpoint `POST /import/csv`
**Priority**: P1 — Exposes parser to users

- Set up FastAPI app scaffold (`src/api.py` or equivalent)
- Add `POST /import/csv` endpoint:
  - Accepts multipart file upload (`UploadFile`)
  - Parses CSV via Issue #6 parser
  - Persists to database using Issue #3 models
  - Upsert logic:
    - `Routine`: deduplicate by name (insert if not exists)
    - `Exercise`: deduplicate by name (insert if not exists)
    - `Workout`: create new ( workouts are assumed unique sessions)
    - `WorkoutExercise`: create new, ordered by `exercise_index`
    - `Set`: create new, ordered by `set_index`
  - Rollback entire transaction on partial failure
  - Return JSON summary: `{ "workouts_imported": N, "exercises_imported": M, "sets_imported": K }`
- Add integration test with a fixture CSV

**Acceptance Criteria**:
- `curl -X POST http://localhost:8000/import/csv -F "file=@sample.csv"` successfully imports data
- Duplicate imports are idempotent (same data produces same result without errors)
- Malformed CSV returns a 4xx error with a clear message
- Integration test passes end-to-end

---

### Wave 3: MCP Server & Tools

#### Issue #8 — Set up MCP server scaffold
**Priority**: P1 — Enables MCP tools

- Integrate `FastMCP` into the application (e.g., `src/mcp_server.py`)
- Configure MCP server for stdio transport (compatible with Claude Desktop, Continue, etc.)
- Server lifecycle:
  - Startup: initialize DB engine/session factory
  - Shutdown: close connections
- Mount MCP server so it can run alongside FastAPI (e.g., via subprocess, or FastAPI serving both)
- Document MCP client configuration in README

**Acceptance Criteria**:
- `python main.py` starts the MCP server
- MCP inspector or Claude Desktop can discover the server
- Server lifecycle hooks work (no connection leaks)

---

#### Issue #9 — Implement workout retrieval MCP tools
**Priority**: P1 — Core query functionality

Implement three structurally similar tools that return filtered workout detail lists:

1. **`get_workout_by_date_range(start_date, end_date)`**
   - Retrieve all workouts whose `start` time falls within the range
   - Return workout details including routine name, exercises performed, and sets

2. **`get_workout_by_routine(routine_name)`**
   - Filter workouts by their associated routine name
   - Return full workout details

3. **`get_workout_by_exercise(exercise_name)`**
   - Return workouts that contain a specific exercise
   - Include full workout details (all exercises and sets) to preserve workout context

Common requirements:
- Proper `@mcp.tool()` decorators with descriptions
- Typed parameters and return types
- Error handling for empty results (return empty list, not error)
- Unit tests per tool with fixture data

**Acceptance Criteria**:
- All three tools are discoverable and callable via MCP client
- Tools return correct data for valid queries
- Empty queries return empty arrays, not errors
- Tests pass

---

#### Issue #10 — Implement workout count and last-workout MCP tools
**Priority**: P1 — Aggregation queries

1. **`get_workout_count(start_date?, end_date?, routine_name?)`**
   - Return total count of workouts
   - Optional filters: date range, routine name
   - Return integer

2. **`get_last_workout(exercise_name?)`**
   - Return the most recent workout overall, or filtered by exercise
   - Return single workout detail object (or null if none)

**Acceptance Criteria**:
- Count tool returns correct integer with and without filters
- Last workout tool returns the chronologically latest workout
- Both handle empty results gracefully
- Tests pass

---

#### Issue #11 — Implement personal record MCP tools
**Priority**: P1 — Performance tracking

1. **`get_min_pr_by_exercise(exercise_name)`**
   - For the given exercise, find the lowest "best set" weight across all workouts
   - "Best set" for a workout = the single heaviest set for that exercise in that workout
   - Return: `{ "date": "...", "weight": 100.0, "reps": 5 }`

2. **`get_max_pr_by_exercise(exercise_name)`**
   - For the given exercise, find the highest "best set" weight across all workouts
   - Same "best set" definition as above
   - Return: `{ "date": "...", "weight": 150.0, "reps": 1 }`

Note: If the user wants PR by volume (weight × reps), we can extend later. For MVP, weight-only PRs are standard.

**Acceptance Criteria**:
- PR calculations are correct and account for per-workout best sets
- Both tools handle exercises with no data gracefully
- Tests cover PR detection across multiple workouts

---

### Wave 4: Polish & Hardening

#### Issue #12 — Comprehensive test coverage and validation
**Priority**: P2 — Quality gate

- Fill test gaps:
  - CSV edge cases: empty file, oversized file, bad encoding, missing columns
  - API error paths: invalid multipart, non-CSV file, DB connection failure
  - DB constraint violations: duplicate unique fields, orphaned records
- Integration tests for the full pipeline: CSV import → MCP query
- Target coverage:
  - Parser: 100%
  - API endpoint: 100%
  - MCP tools: ≥90%
  - Models: 100%
- Add coverage report to CI

**Acceptance Criteria**:
- `pytest --cov` shows ≥90% coverage on core logic (parser, API, MCP tools, models)
- CI enforces a coverage threshold
- All edge cases are tested

---

#### Issue #13 — Error handling, logging, and production readiness
**Priority**: P2 — Operational quality

- FastAPI exception handlers:
  - `ValidationError` → 422 with clear messages
  - `IntegrityError` → 409 or 422
  - Generic exceptions → 500 with safe message (log full traceback)
- Structured logging:
  - Use Python `logging` with JSON formatter option
  - Log levels: DEBUG for queries, INFO for imports, ERROR for failures
  - Include request IDs or correlation IDs
- MCP tool error handling:
  - Meaningful error strings for AI agents (not stack traces)
- Configuration management:
  - All settings via environment variables with `.env` support
  - Sensible defaults for local development
  - Document all config vars in README

**Acceptance Criteria**:
- Errors return consistent, user-friendly messages
- Logs are readable and useful for debugging
- MCP tool errors explain what went wrong to AI agents
- No hardcoded secrets or config values

---

#### Issue #14 — Documentation and usage examples
**Priority**: P2 — Developer experience

- Update `README.md`:
  - Complete setup instructions (clone, install, DB setup, run server)
  - Full environment variable reference
  - MCP client configuration examples (Claude Desktop JSON, Continue, etc.)
- Add example queries for each MCP tool:
  - "Show me all chest workouts from last month"
  - "What's my heaviest squat this year?"
  - etc.
- Add `.env.example` file

**Acceptance Criteria**:
- A new developer can clone, configure, and run the server without external help
- All MCP tools have documented usage examples
- README is accurate and up-to-date with the implementation

---

## Dependencies Between Issues

```
Issue #1 (tooling)
  └─> Issue #2 (CI)

Issue #3 (models)
  └─> Issue #4 (migrations)
       └─> Issue #5 (test infra)
            └─> Issue #6 (parser)
                 └─> Issue #7 (API endpoint)
            └─> Issue #8 (MCP scaffold)
                 └─> Issue #9 (retrieval tools)
                 └─> Issue #10 (count/last tools)
                 └─> Issue #11 (PR tools)

Issue #7, #9, #10, #11
  └─> Issue #12 (test coverage)
  └─> Issue #13 (error handling)
  └─> Issue #14 (docs)
```

## Suggested Implementation Order

1. #1, #2 (tooling + CI) — parallelizable
2. #3, #4 (models + migrations) — sequential
3. #5 (test infra) — after #4
4. #6, #8 (parser + MCP scaffold) — parallelizable after #5
5. #7 (API endpoint) — after #6
6. #9, #10, #11 (MCP tools) — parallelizable after #8
7. #12, #13, #14 (polish) — after all feature issues

## Notes

- All issues should reference this design doc for context
- Consider adding a sample Hevy CSV fixture to `tests/fixtures/` for consistent testing
- The parser should handle both kg and lbs; we may need to store unit preference or normalize
- MCP tools should return structured data (dictionaries/JSON) so AI agents can interpret results
- Consider pagination for tools that return lists (Issue #9), especially for large workout histories
