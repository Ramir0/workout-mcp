# Wave 4 — Polish & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the workout-mcp server for production with comprehensive tests, structured logging, error handling, and complete documentation.

**Architecture:** Sequential implementation — tests first (baseline coverage), then error handling/logging (verify with tests), then docs (reflect final state). Uses `structlog` for structured logging, `pydantic-settings` for typed config.

**Tech Stack:** Python 3.13, uv, structlog, pydantic-settings, FastAPI, SQLAlchemy 2.0, PostgreSQL, pytest, pytest-cov

---

## Assumptions & Decisions

| # | Assumption |
|---|------------|
| A | MCP tools return `{"error": "..."}` dicts on failure — not raised exceptions. AI agents get structured error info. |
| B | Logging uses `structlog` with JSON renderer (production) and console renderer (development). |
| C | Config uses `pydantic-settings` with `.env` auto-loading. Replaces raw `os.getenv()`. |
| D | Coverage threshold is 90% enforced in CI via `--cov-fail-under=90`. |
| E | Implementation order: Issue #16 → #17 → #18 (tests → error handling → docs). |

---

## Issue #16: Comprehensive Test Coverage

### Task 16.1: Add pyproject.toml coverage configuration

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest-cov configuration to pyproject.toml**

Add to `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

Add coverage configuration:

```toml
[tool.coverage.run]
source = ["workout_mcp"]

[tool.coverage.report]
fail_under = 90
show_missing = true
```

- [ ] **Step 2: Verify pytest runs with coverage**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest --cov --cov-report=term-missing`
Expected: Tests pass, coverage report shown

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pytest-cov configuration with 90% threshold"
```

---

### Task 16.2: Create tests/test_config.py

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

```python
"""Tests for workout_mcp.config module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_settings_loads_defaults() -> None:
    """Settings loads default values when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        # Re-import to get fresh settings
        from workout_mcp.config import Settings

        settings = Settings()
        assert settings.database_url == "postgresql://postgres:postgres@localhost:5432/workout_mcp"
        assert settings.test_database_url == "postgresql://postgres:postgres@localhost:5432/workout_mcp_test"
        assert settings.app_port == 8000
        assert settings.log_level == "INFO"
        assert settings.log_format == "console"


def test_settings_env_override() -> None:
    """Settings values can be overridden via environment variables."""
    env = {
        "DATABASE_URL": "postgresql://custom:custom@localhost:5432/custom_db",
        "APP_PORT": "9000",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=True):
        from workout_mcp.config import Settings

        settings = Settings()
        assert settings.database_url == "postgresql://custom:custom@localhost:5432/custom_db"
        assert settings.app_port == 9000
        assert settings.log_level == "DEBUG"


def test_settings_invalid_port() -> None:
    """Settings raises ValidationError for invalid port."""
    with patch.dict(os.environ, {"APP_PORT": "not_a_number"}, clear=True):
        from workout_mcp.config import Settings

        with pytest.raises(Exception):  # ValidationError
            Settings()
```

- [ ] **Step 2: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add config module tests"
```

---

### Task 16.3: Create tests/test_main.py

**Files:**
- Create: `tests/test_main.py`

- [ ] **Step 1: Write main module tests**

```python
"""Tests for main.py — app mounting and lifespan."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_has_correct_title() -> None:
    """FastAPI app has the expected title."""
    from workout_mcp.api import app

    assert app.title == "Workout MCP Server"


def test_mcp_server_is_mounted() -> None:
    """MCP server is mounted at /mcp."""
    from workout_mcp.api import app

    # Check that /mcp route exists
    mcp_routes = [r for r in app.routes if hasattr(r, "path") and r.path == "/mcp"]
    assert len(mcp_routes) > 0


def test_health_endpoint() -> None:
    """FastAPI app is accessible."""
    from workout_mcp.api import app

    client = TestClient(app)
    # POST /import/csv with no file should return 422 (validation error)
    response = client.post("/import/csv")
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_main.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_main.py
git commit -m "test: add main module tests"
```

---

### Task 16.4: Expand tests/test_api.py with error paths

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add non-UTF8 encoding test**

Append to `tests/test_api.py`:

```python
def test_import_non_utf8_file(client: TestClient) -> None:
    """Non-UTF8 encoded file returns 400."""
    # Create a file with invalid UTF-8 bytes
    import io

    content = b"\x80\x81\x82\x83"
    files = {"file": ("test.csv", io.BytesIO(content), "text/csv")}
    response = client.post("/import/csv", files=files)
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_import_invalid_multipart(client: TestClient) -> None:
    """Missing file field returns 422."""
    response = client.post("/import/csv")
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_api.py -v`
Expected: All tests PASS (including new ones)

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add API error path tests"
```

---

### Task 16.5: Expand tests/test_mcp_tools.py with error paths

**Files:**
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Add malformed date tests**

Append to `tests/test_mcp_tools.py`:

```python
def test_get_workout_by_date_range_malformed_dates(db_session: Session) -> None:
    """Malformed date strings return error dict."""
    from workout_mcp.mcp_server import _get_workout_by_date_range

    result = _get_workout_by_date_range(db_session, "not-a-date", "2025-01-01")
    assert isinstance(result, dict)
    assert "error" in result


def test_get_workout_count_malformed_date(db_session: Session) -> None:
    """Malformed date in count query returns error dict."""
    from workout_mcp.mcp_server import _get_workout_count

    result = _get_workout_count(db_session, start_date="bad-date")
    assert isinstance(result, dict)
    assert "error" in result
```

Note: These tests will initially fail because the `_get_*` functions don't have error handling yet. They'll pass after Issue #17 is implemented. For now, you can skip them or mark them with `@pytest.mark.xfail`.

- [ ] **Step 2: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_mcp_tools.py -v`
Expected: Existing tests pass, new tests fail (expected — will pass after Issue #17)

- [ ] **Step 3: Commit**

```bash
git add tests/test_mcp_tools.py
git commit -m "test: add MCP tool error path tests (xfail until error handling)"
```

---

### Task 16.6: Update CI workflow for coverage enforcement

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Update test job to enforce coverage**

Replace the test job's `Run tests` step:

```yaml
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/workout_mcp_test
        run: uv run pytest --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=90
```

- [ ] **Step 2: Verify CI config is valid YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: enforce 90% coverage threshold in test job"
```

---

## Issue #17: Error Handling, Logging & Production Readiness

### Task 17.1: Add new dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add structlog and pydantic-settings to dependencies**

Update `[project.dependencies]` in `pyproject.toml`:

```toml
dependencies = [
    "httpx>=0.28.1",
    "mcp[cli]>=1.27.1",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "python-dotenv>=1.0",
    "fastapi>=0.115",
    "python-multipart>=0.0.12",
    "uvicorn>=0.32",
    "structlog>=24.1.0",
    "pydantic-settings>=2.0.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "import structlog; from pydantic_settings import BaseSettings; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add structlog and pydantic-settings"
```

---

### Task 17.2: Rewrite config.py with pydantic-settings

**Files:**
- Modify: `workout_mcp/config.py`
- Modify: `tests/conftest.py` (update imports)

- [ ] **Step 1: Rewrite config.py**

Replace `workout_mcp/config.py` entirely:

```python
"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/workout_mcp"
    test_database_url: str = "postgresql://postgres:postgres@localhost:5432/workout_mcp_test"
    app_port: int = 8000
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

# Backward-compatible exports for existing code
DATABASE_URL: str = settings.database_url
TEST_DATABASE_URL: str = settings.test_database_url
```

- [ ] **Step 2: Update conftest.py to use new config**

Update `tests/conftest.py` line 10:

```python
from workout_mcp.config import settings
```

And update line 17 to use `settings.test_database_url`:

```python
    engine = create_engine(settings.test_database_url)
```

- [ ] **Step 3: Run type checker**

Run: `uv run mypy workout_mcp/config.py tests/conftest.py`
Expected: PASS

- [ ] **Step 4: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/config.py tests/conftest.py
git commit -m "feat: rewrite config with pydantic-settings"
```

---

### Task 17.3: Create logging module

**Files:**
- Create: `workout_mcp/logging.py`

- [ ] **Step 1: Create logging.py with structlog configuration**

```python
"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog

from workout_mcp.config import settings


def setup_logging() -> None:
    """Configure structlog for the application.

    - JSON renderer in production (log_format=json)
    - Console renderer in development (log_format=console)
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        # Production: JSON output
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        # Development: console output
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=shared_processors,
        )

    # Apply formatter to root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger bound to the given name."""
    return structlog.get_logger(name)
```

- [ ] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/logging.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add workout_mcp/logging.py
git commit -m "feat: add structlog logging module"
```

---

### Task 17.4: Add logging setup to main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add logging initialization to main.py**

Replace `main.py`:

```python
"""Entry point for the Workout MCP Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from starlette.routing import Mount

from workout_mcp.api import app
from workout_mcp.logging import setup_logging
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
    setup_logging()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run type checker**

Run: `uv run mypy main.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: initialize structlog on startup"
```

---

### Task 17.5: Add FastAPI exception handlers to api.py

**Files:**
- Modify: `workout_mcp/api.py`

- [ ] **Step 1: Add exception handlers**

Add to `workout_mcp/api.py` after the `app` creation:

```python
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from workout_mcp.logging import get_logger

logger = get_logger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Return 422 with field-level validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request, exc):
    """Return 409 for database constraint violations."""
    logger.error("integrity_error", error=str(exc))
    return JSONResponse(
        status_code=409,
        content={"detail": "Duplicate resource or constraint violation"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Return 500 with safe message for unhandled exceptions."""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
```

Also replace the existing `logger = logging.getLogger(__name__)` line and the `logger.exception()` call with structlog:

```python
# Replace:
# import logging
# logger = logging.getLogger(__name__)

# With:
from workout_mcp.logging import get_logger
logger = get_logger(__name__)
```

And update the `SQLAlchemyError` handler:

```python
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("database_import_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Database error during import") from exc
```

- [ ] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/api.py`
Expected: PASS

- [ ] **Step 3: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_api.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add workout_mcp/api.py
git commit -m "feat: add FastAPI exception handlers with structlog"
```

---

### Task 17.6: Add request logging middleware

**Files:**
- Modify: `workout_mcp/api.py`

- [ ] **Step 1: Add middleware after exception handlers**

```python
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)
```

- [ ] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/api.py`
Expected: PASS

- [ ] **Step 3: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_api.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add workout_mcp/api.py
git commit -m "feat: add request logging middleware with structlog"
```

---

### Task 17.7: Add error handling to MCP tools

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [ ] **Step 1: Add imports and logger**

Add to top of `workout_mcp/mcp_server.py`:

```python
from sqlalchemy.exc import SQLAlchemyError
from workout_mcp.logging import get_logger

log = get_logger(__name__)
```

- [ ] **Step 2: Add error handling to each MCP tool**

Wrap each `@mcp.tool()` function. Example for `get_workout_by_date_range`:

```python
@mcp.tool()
def get_workout_by_date_range(start_date: str, end_date: str) -> list[dict[str, object]] | dict[str, str]:
    """Retrieve all workouts within a date range.

    Returns full workout details including routine name, exercises, and sets.
    Dates should be in ISO format (YYYY-MM-DD).
    """
    try:
        with get_db_session() as db:
            return _get_workout_by_date_range(db, start_date, end_date)
    except ValueError as exc:
        log.error("invalid_parameters", tool="get_workout_by_date_range", error=str(exc))
        return {"error": f"Invalid parameters: {exc}"}
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_workout_by_date_range", error=str(exc))
        return {"error": "Database query failed"}
```

Apply the same pattern to all 7 tools:
- `get_workout_by_date_range` — catch ValueError, SQLAlchemyError
- `get_workout_by_routine` — catch SQLAlchemyError
- `get_workout_by_exercise` — catch SQLAlchemyError
- `get_workout_count` — catch ValueError, SQLAlchemyError
- `get_last_workout` — catch SQLAlchemyError
- `get_max_pr_by_exercise` — catch SQLAlchemyError
- `get_min_pr_by_exercise` — catch SQLAlchemyError

- [ ] **Step 3: Run type checker**

Run: `uv run mypy workout_mcp/mcp_server.py`
Expected: PASS

- [ ] **Step 4: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_mcp_tools.py -v`
Expected: All tests PASS (including previously xfail tests)

- [ ] **Step 5: Remove xfail markers from error path tests**

Remove `@pytest.mark.xfail` from the tests added in Task 16.5.

- [ ] **Step 6: Commit**

```bash
git add workout_mcp/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: add error handling to all MCP tools"
```

---

### Task 17.8: Update database.py to use settings

**Files:**
- Modify: `workout_mcp/database.py`

- [ ] **Step 1: Update database.py imports**

Replace `workout_mcp/database.py`:

```python
"""Database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workout_mcp.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

- [ ] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/database.py`
Expected: PASS

- [ ] **Step 3: Run tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add workout_mcp/database.py
git commit -m "refactor: use settings object in database.py"
```

---

### Task 17.9: Run full test suite with coverage

**Files:** None

- [ ] **Step 1: Run full test suite with coverage**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest --cov --cov-report=term-missing --cov-fail-under=90`
Expected: All tests PASS, coverage ≥90%

- [ ] **Step 2: If coverage is below 90%, identify gaps and add tests**

Check the coverage report for any modules below target. Add tests as needed.

- [ ] **Step 3: Run linter and type checker**

Run: `uv run ruff check . && uv run mypy .`
Expected: Both PASS

- [ ] **Step 4: Run all pre-commit hooks**

Run: `uv run pre-commit run --all-files`
Expected: All hooks PASS

- [ ] **Step 5: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: lint and type errors for wave 4"
```

---

## Issue #18: Documentation & Usage Examples

### Task 18.1: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example with all settings**

Replace `.env.example`:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres

# App
APP_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: update .env.example with all settings"
```

---

### Task 18.2: Update README.md — Environment Variables

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add environment variable reference section**

Add a section after "Local Development":

```markdown
## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/workout_mcp` | PostgreSQL connection string |
| `TEST_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/workout_mcp_test` | Test database connection string |
| `APP_PORT` | `8000` | Port for the FastAPI server |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `console` | Log output format (`console` for dev, `json` for production) |

Copy `.env.example` to `.env` and adjust values for your environment.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add environment variable reference to README"
```

---

### Task 18.3: Update README.md — MCP Client Configuration

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add MCP client configuration examples**

Add a section with JSON configs:

```markdown
## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "workout": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Continue

Add to `.continue/config.yaml`:

```yaml
mcpServers:
  - name: workout
    url: http://localhost:8000/mcp
```

### Generic MCP Client

Any MCP-compatible client can connect to `http://localhost:8000/mcp` using streamable HTTP transport.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add MCP client configuration examples"
```

---

### Task 18.4: Update README.md — Example Queries

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add example queries section**

```markdown
## Example Queries

Once connected via MCP, you can ask questions like:

| Natural Language Query | MCP Tool Called |
|------------------------|-----------------|
| "Show me all chest workouts from last month" | `get_workout_by_exercise("Chest Press")` |
| "What's my heaviest squat this year?" | `get_max_pr_by_exercise("Squat")` |
| "How many workouts did I do this week?" | `get_workout_count(start_date="2026-05-12", end_date="2026-05-19")` |
| "What was my last workout?" | `get_last_workout()` |
| "Show me all PPL routine workouts" | `get_workout_by_routine("PPL")` |
| "What's my lightest bench press PR?" | `get_min_pr_by_exercise("Bench Press")` |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add MCP example queries"
```

---

### Task 18.5: Final verification

**Files:** None

- [ ] **Step 1: Run full test suite with coverage**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest --cov --cov-report=term-missing --cov-fail-under=90`
Expected: All tests PASS, coverage ≥90%

- [ ] **Step 2: Run all pre-commit hooks**

Run: `uv run pre-commit run --all-files`
Expected: All hooks PASS

- [ ] **Step 3: Verify README accuracy**

Read through README.md and verify:
- All commands work
- All env vars are documented
- MCP config examples are correct
- Example queries match actual tool signatures

- [ ] **Step 4: Final commit if needed**

```bash
git add -A
git commit -m "chore: final polish for wave 4"
```

---

## File Summary

| File | Action | Issue |
|------|--------|-------|
| `pyproject.toml` | Modify | #16, #17 |
| `tests/test_config.py` | Create | #16 |
| `tests/test_main.py` | Create | #16 |
| `tests/test_api.py` | Modify | #16 |
| `tests/test_mcp_tools.py` | Modify | #16, #17 |
| `.github/workflows/ci.yml` | Modify | #16 |
| `workout_mcp/config.py` | Modify | #17 |
| `workout_mcp/logging.py` | Create | #17 |
| `workout_mcp/api.py` | Modify | #17 |
| `workout_mcp/mcp_server.py` | Modify | #17 |
| `workout_mcp/database.py` | Modify | #17 |
| `main.py` | Modify | #17 |
| `tests/conftest.py` | Modify | #17 |
| `.env.example` | Modify | #18 |
| `README.md` | Modify | #18 |
