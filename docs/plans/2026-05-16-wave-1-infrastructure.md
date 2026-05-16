# Wave 1 — Infrastructure & Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up development tooling, CI, SQLAlchemy ORM models, Alembic migrations, and test infrastructure to create a working foundation for the Workout MCP Server.

**Architecture:** SQLAlchemy 2.0 ORM with `Mapped[]` type annotations, PostgreSQL backend, Alembic for schema migrations, pytest with transaction-isolated database fixtures for reliable testing.

**Tech Stack:** Python 3.13, uv, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest, ruff, mypy, pre-commit, GitHub Actions

---

## File Structure

```
workout-mcp/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Issue #2 — GitHub Actions
├── alembic/
│   ├── env.py                        # Issue #4 — Alembic configuration
│   ├── script.py.mako                # Issue #4 — Alembic template
│   └── versions/                     # Issue #4 — Migration scripts
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Issue #5 — Pytest fixtures
│   ├── test_models.py                # Issue #3 — Model unit tests
│   └── test_database.py              # Issue #5 — Integration tests
├── workout_mcp/                      # Issue #3 — Application package
│   ├── __init__.py
│   ├── models.py                     # Issue #3 — SQLAlchemy ORM models
│   ├── database.py                   # Issue #4 — Engine & session factory
│   └── config.py                     # Issue #4 — Settings & env vars
├── .env.example                      # Issue #4 — Environment template
├── .pre-commit-config.yaml           # Issue #1 — Pre-commit hooks
├── main.py                           # Existing — entry point stub
└── pyproject.toml                    # Issue #1, #3, #4 — Tool & dep config
```

---

## Issue #1: Development Tooling Setup

### Task 1.1: Configure pyproject.toml with dev dependencies and tool settings

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add build system and dev dependency group**

Add `[build-system]` and `[dependency-groups]` to `pyproject.toml`. The full file should be:

```toml
[project]
name = "workout-mcp"
version = "0.1.0"
description = "MCP server + REST API for ingesting and querying workout data from Hevy CSV exports"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.28.1",
    "mcp[cli]>=1.27.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["workout_mcp"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
]
```

- [ ] **Step 2: Add ruff configuration**

Append to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 100
select = [
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = ["E501"]  # Line too long — handled by formatter

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

- [ ] **Step 3: Add mypy configuration**

Append to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
ignore_missing_imports = true
```

- [ ] **Step 4: Add pytest configuration**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

- [ ] **Step 5: Install dependencies**

Run: `uv sync`
Expected: Dependencies install successfully, `.venv` created/updated.

- [ ] **Step 6: Verify tool availability**

Run: `uv run ruff --version`
Expected: `ruff x.y.z`

Run: `uv run mypy --version`
Expected: `mypy x.y.z`

Run: `uv run pytest --version`
Expected: `pytest x.y.z`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml
uv lock  # Update uv.lock with new deps
git add uv.lock
git commit -m "chore: add dev tooling dependencies (pytest, ruff, mypy, pre-commit)"
```

---

### Task 1.2: Create pre-commit configuration and install hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies: [types-python-dateutil]
```

- [ ] **Step 2: Install pre-commit hooks**

Run: `uv run pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 3: Run pre-commit on all files**

Run: `uv run pre-commit run --all-files`
Expected: All hooks pass (there may be warnings about missing `tests/` or `workout_mcp/`, which is expected).

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit configuration"
```

---

### Task 1.3: Verify tooling passes on existing code

**Files:**
- Modify: `main.py` (if needed to satisfy tooling)

- [ ] **Step 1: Run ruff check**

Run: `uv run ruff check .`
Expected: PASS (no errors on `main.py`)

If ruff reports issues in `main.py`, fix them. Current `main.py`:

```python
def main() -> None:
    print("Hello from workout-mcp!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run mypy**

Run: `uv run mypy .`
Expected: PASS (no errors, possibly "Found 1 source file" or similar)

If mypy reports missing imports for `mcp`, add to `[tool.mypy]`:

```toml
[[tool.mypy.overrides]]
module = ["mcp.*"]
follow_untyped_imports = true
```

- [ ] **Step 3: Run pytest**

Run: `uv run pytest`
Expected: `collected 0 items` or similar — no tests yet, but pytest runs without error.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: verify tooling passes on existing code"
```

---

## Issue #2: GitHub Actions CI Pipeline

### Task 2.1: Create CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create directories**

Run: `mkdir -p .github/workflows`

- [ ] **Step 2: Create ci.yml**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Run ruff
        run: uv run ruff check .

      - name: Run ruff format check
        run: uv run ruff format --check .

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Run mypy
        run: uv run mypy .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: workout_mcp_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/workout_mcp_test
        run: uv run pytest --cov=workout_mcp --cov-report=term-missing
```

- [ ] **Step 3: Verify YAML syntax**

Run: `uv run pre-commit run check-yaml --all-files`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for lint, typecheck, and test"
```

---

### Task 2.2: Test CI locally (optional but recommended)

**Files:** None

- [ ] **Step 1: Install act (optional)**

If `act` is available locally, run: `act -j lint`
Expected: Lint job passes.

If `act` is not available, skip this step and rely on the first PR to validate.

- [ ] **Step 2: Push to verify**

```bash
git push origin main  # or create a test PR
```

Expected: GitHub Actions runs and all three jobs (lint, typecheck, test) appear. The test job may fail initially because `workout_mcp/` and tests don't exist yet — this is expected and will be resolved in later issues.

---

## Issue #3: Define SQLAlchemy ORM Models

### Task 3.1: Add SQLAlchemy dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add sqlalchemy to dependencies**

Add `"sqlalchemy>=2.0"` to the `[project] dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "httpx>=0.28.1",
    "mcp[cli]>=1.27.1",
    "sqlalchemy>=2.0",
]
```

- [ ] **Step 2: Install**

Run: `uv sync`
Expected: SQLAlchemy installs.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add sqlalchemy>=2.0"
```

---

### Task 3.2: Create application package and models

**Files:**
- Create: `workout_mcp/__init__.py`
- Create: `workout_mcp/models.py`

- [ ] **Step 1: Create workout_mcp/__init__.py**

```python
"""Workout MCP Server package."""
```

- [ ] **Step 2: Create workout_mcp/models.py**

```python
"""SQLAlchemy ORM models for workout data."""

from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Routine(Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    workouts: Mapped[List["Workout"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Routine(id={self.id!r}, name={self.name!r})"


class Workout(Base):
    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime]
    end: Mapped[datetime]
    routine_id: Mapped[int] = mapped_column(ForeignKey("routine.id"))

    routine: Mapped["Routine"] = relationship(back_populates="workouts")
    workout_exercises: Mapped[List["WorkoutExercise"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Workout(id={self.id!r}, start={self.start!r}, end={self.end!r})"


class Exercise(Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    workout_exercises: Mapped[List["WorkoutExercise"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Exercise(id={self.id!r}, name={self.name!r})"


class WorkoutExercise(Base):
    __tablename__ = "workout_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workout.id"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"))
    exercise_index: Mapped[int]

    workout: Mapped["Workout"] = relationship(back_populates="workout_exercises")
    exercise: Mapped["Exercise"] = relationship(back_populates="workout_exercises")
    sets: Mapped[List["Set"]] = relationship(
        back_populates="workout_exercise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"WorkoutExercise(id={self.id!r}, "
            f"exercise_index={self.exercise_index!r})"
        )


class Set(Base):
    __tablename__ = "set"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercise.id"))
    set_index: Mapped[int]
    reps: Mapped[int]
    weight: Mapped[float]
    rpe: Mapped[float | None] = mapped_column(default=None)

    workout_exercise: Mapped["WorkoutExercise"] = relationship(back_populates="sets")

    def __repr__(self) -> str:
        return (
            f"Set(id={self.id!r}, set_index={self.set_index!r}, "
            f"reps={self.reps!r}, weight={self.weight!r})"
        )
```

- [ ] **Step 3: Run ruff on new code**

Run: `uv run ruff check workout_mcp/`
Expected: PASS

- [ ] **Step 4: Run mypy on new code**

Run: `uv run mypy workout_mcp/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/
git commit -m "feat: add SQLAlchemy ORM models for Routine, Workout, Exercise, WorkoutExercise, Set"
```

---

### Task 3.3: Write unit tests for models

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Create tests/__init__.py**

```python
"""Tests package."""
```

- [ ] **Step 2: Write failing test**

Create `tests/test_models.py`:

```python
"""Unit tests for SQLAlchemy models (no database required)."""

from datetime import datetime

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_routine_instantiation() -> None:
    routine = Routine(name="Push Day")
    assert routine.name == "Push Day"
    assert routine.id is None


def test_workout_instantiation() -> None:
    start = datetime(2024, 1, 1, 10, 0, 0)
    end = datetime(2024, 1, 1, 11, 0, 0)
    workout = Workout(start=start, end=end)
    assert workout.start == start
    assert workout.end == end


def test_exercise_instantiation() -> None:
    exercise = Exercise(name="Bench Press")
    assert exercise.name == "Bench Press"


def test_workout_exercise_instantiation() -> None:
    we = WorkoutExercise(exercise_index=0)
    assert we.exercise_index == 0


def test_set_instantiation() -> None:
    set_ = Set(set_index=1, reps=10, weight=100.0, rpe=8.0)
    assert set_.reps == 10
    assert set_.weight == 100.0
    assert set_.rpe == 8.0


def test_set_optional_rpe() -> None:
    set_ = Set(set_index=1, reps=10, weight=100.0)
    assert set_.rpe is None


def test_relationship_backrefs() -> None:
    routine = Routine(name="Leg Day")
    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
    )
    workout.routine = routine
    assert workout in routine.workouts
    assert workout.routine is routine
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add model instantiation and relationship unit tests"
```

---

## Issue #4: Set Up Database Configuration and Alembic Migrations

### Task 4.1: Add database dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add psycopg2-binary and alembic**

Add to `[project] dependencies`:

```toml
dependencies = [
    "httpx>=0.28.1",
    "mcp[cli]>=1.27.1",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "python-dotenv>=1.0",
]
```

- [ ] **Step 2: Install**

Run: `uv sync`
Expected: psycopg2-binary, alembic, python-dotenv install.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add psycopg2-binary, alembic, python-dotenv"
```

---

### Task 4.2: Create configuration and database modules

**Files:**
- Create: `workout_mcp/config.py`
- Create: `workout_mcp/database.py`

- [ ] **Step 1: Create config.py**

```python
"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/workout_mcp",
)

TEST_DATABASE_URL: str = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://localhost:5432/workout_mcp_test",
)
```

- [ ] **Step 2: Create database.py**

```python
"""Database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workout_mcp.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

- [ ] **Step 3: Create .env.example**

```bash
DATABASE_URL=postgresql://localhost:5432/workout_mcp
TEST_DATABASE_URL=postgresql://localhost:5432/workout_mcp_test
```

- [ ] **Step 4: Verify type checking**

Run: `uv run mypy workout_mcp/config.py workout_mcp/database.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/config.py workout_mcp/database.py .env.example
git commit -m "feat: add database configuration with env-based settings"
```

---

### Task 4.3: Initialize and configure Alembic

**Files:**
- Modify: `pyproject.toml`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/README`
- Create: `alembic/versions/.gitkeep`

- [ ] **Step 1: Initialize Alembic**

Run: `uv run alembic init alembic`
Expected: Creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README`, and `alembic/versions/`.

- [ ] **Step 2: Configure alembic.ini**

Find the `sqlalchemy.url` line in `alembic.ini` and change it to:

```ini
sqlalchemy.url = postgresql://localhost:5432/workout_mcp
```

Also verify `script_location = alembic` is set.

- [ ] **Step 3: Configure alembic/env.py**

Replace the contents of `alembic/env.py` with:

```python
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from workout_mcp.config import DATABASE_URL
from workout_mcp.models import Base

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with environment-aware default
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Ensure versions directory exists**

Run: `touch alembic/versions/.gitkeep`

- [ ] **Step 5: Commit Alembic scaffolding**

```bash
git add alembic.ini alembic/ .env.example
git commit -m "chore: initialize Alembic with model metadata"
```

---

### Task 4.4: Create initial migration

**Files:**
- Create: `alembic/versions/xxxx_initial_migration.py` (auto-generated)

**Prerequisite:** PostgreSQL must be running locally. If not available, install Docker or use a local PostgreSQL instance.

- [ ] **Step 1: Ensure PostgreSQL is running**

Run: `pg_isready -h localhost -p 5432`
Expected: `localhost:5432 - accepting connections`

If PostgreSQL is not running, start it (e.g., via Docker):

```bash
docker run -d --name workout-postgres \
  -e POSTGRES_DB=workout_mcp \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:16
```

- [ ] **Step 2: Create the database if it doesn't exist**

Run: `createdb -h localhost -U postgres workout_mcp || true`
Expected: Database created (or already exists).

- [ ] **Step 3: Generate initial migration**

Run: `uv run alembic revision --autogenerate -m "Initial migration: create routine, workout, exercise, workout_exercise, set tables"`
Expected: Creates a new file in `alembic/versions/`.

- [ ] **Step 4: Review the generated migration**

Read the generated file in `alembic/versions/`. It should contain `upgrade()` with `op.create_table` for all 5 tables and `downgrade()` with `op.drop_table` for all 5 tables. Verify foreign keys and indexes are present.

- [ ] **Step 5: Apply the migration**

Run: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Context impl PostgresqlImpl... Running upgrade  -> <revision>, Initial migration...`

- [ ] **Step 6: Verify tables were created**

Run: `psql -h localhost -U postgres -d workout_mcp -c "\dt"`
Expected: Lists `routine`, `workout`, `exercise`, `workout_exercise`, `set`, and `alembic_version`.

- [ ] **Step 7: Test downgrade**

Run: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic downgrade -1`
Expected: Tables are dropped.

Verify: `psql -h localhost -U postgres -d workout_mcp -c "\dt"` should show only `alembic_version` or be empty.

- [ ] **Step 8: Re-apply upgrade**

Run: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head`
Expected: Tables recreated.

- [ ] **Step 9: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add initial Alembic migration for all 5 tables"
```

---

## Issue #5: Create Test Infrastructure

### Task 5.1: Create pytest fixtures with transaction isolation

**Files:**
- Create: `tests/conftest.py`

**Prerequisite:** PostgreSQL must be running locally (see Task 4.4).

- [ ] **Step 1: Create the test database**

Run: `createdb -h localhost -U postgres workout_mcp_test || true`
Expected: Database created (or already exists).

- [ ] **Step 2: Create conftest.py**

```python
"""Pytest fixtures and configuration."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from workout_mcp.config import TEST_DATABASE_URL
from workout_mcp.models import Base, Exercise, Routine, Set, Workout, WorkoutExercise


@pytest.fixture(scope="session")
def db_engine() -> Generator:
    """Create a test database engine and schema (once per session)."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Yield a database session with automatic transaction rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()

    # Bind the session to the connection (not the engine)
    session = sessionmaker(bind=connection)()

    # Prevent the session from committing externally
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

- [ ] **Step 3: Verify conftest.py type checks**

Run: `uv run mypy tests/conftest.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add pytest fixtures with transaction rollback isolation"
```

---

### Task 5.2: Write database integration tests

**Files:**
- Create: `tests/test_database.py`

- [ ] **Step 1: Write integration test for round-trip**

```python
"""Database integration tests verifying ORM round-trips."""

from datetime import datetime

from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_create_routine(db_session: Session) -> None:
    routine = Routine(name="Test Routine")
    db_session.add(routine)
    db_session.commit()

    result = db_session.query(Routine).filter_by(name="Test Routine").first()
    assert result is not None
    assert result.name == "Test Routine"


def test_create_workout_with_routine(db_session: Session) -> None:
    routine = Routine(name="Push Day")
    db_session.add(routine)
    db_session.commit()

    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
        routine=routine,
    )
    db_session.add(workout)
    db_session.commit()

    result = db_session.query(Workout).filter_by(routine_id=routine.id).first()
    assert result is not None
    assert result.routine.name == "Push Day"


def test_create_full_workout_hierarchy(db_session: Session) -> None:
    routine = Routine(name="Leg Day")
    db_session.add(routine)
    db_session.commit()

    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
        routine=routine,
    )
    db_session.add(workout)
    db_session.commit()

    exercise = Exercise(name="Squat")
    db_session.add(exercise)
    db_session.commit()

    workout_exercise = WorkoutExercise(
        workout=workout,
        exercise=exercise,
        exercise_index=0,
    )
    db_session.add(workout_exercise)
    db_session.commit()

    set_ = Set(
        workout_exercise=workout_exercise,
        set_index=1,
        reps=5,
        weight=100.0,
        rpe=8.0,
    )
    db_session.add(set_)
    db_session.commit()

    # Verify round-trip
    result_set = db_session.query(Set).filter_by(weight=100.0).first()
    assert result_set is not None
    assert result_set.workout_exercise.exercise.name == "Squat"
    assert result_set.workout_exercise.workout.routine.name == "Leg Day"


def test_transaction_isolation(db_session: Session) -> None:
    """Ensure data from this test is not visible in other tests."""
    routine = Routine(name="Isolation Test")
    db_session.add(routine)
    db_session.commit()

    count = db_session.query(Routine).filter_by(name="Isolation Test").count()
    assert count == 1
```

- [ ] **Step 2: Run integration tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_database.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 3: Verify full test suite**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest -v`
Expected: All tests PASS (7 unit tests + 4 integration tests = 11 total).

- [ ] **Step 4: Commit**

```bash
git add tests/test_database.py
git commit -m "test: add database integration tests for ORM round-trip and isolation"
```

---

### Task 5.3: Verify CI pipeline with new tests

**Files:** None

- [ ] **Step 1: Ensure local tooling passes**

Run: `uv run ruff check .`
Expected: PASS

Run: `uv run mypy .`
Expected: PASS

Run: `uv run pytest -v`
Expected: All tests PASS

Run: `uv run pre-commit run --all-files`
Expected: All hooks PASS

- [ ] **Step 2: Push to trigger CI**

```bash
git push origin main
```

Expected: GitHub Actions CI runs. All three jobs (lint, typecheck, test) should now PASS because `workout_mcp/`, `tests/`, and database fixtures exist.

- [ ] **Step 3: Verify CI results**

Check the GitHub Actions page. All jobs should be green.

---

## Self-Review

### 1. Spec Coverage

| Spec Requirement | Implementing Task |
|---|---|
| Add pytest, ruff, mypy, pytest-cov, pre-commit to dev deps | Task 1.1, Step 1 |
| Configure ruff rules (isort, pyupgrade, flake8-equivalent) | Task 1.1, Step 2 |
| Configure mypy with strict mode | Task 1.1, Step 3 |
| Add pre-commit hooks | Task 1.2 |
| Create test directory structure | Task 1.1 (pytest config), Task 3.3, Task 5.1 |
| GitHub Actions CI (lint, typecheck, test) | Task 2.1 |
| Cache uv dependencies | Task 2.1 (astral-sh/setup-uv handles caching) |
| Define 5 SQLAlchemy models with Mapped[] | Task 3.2 |
| Relationships with backrefs | Task 3.2 |
| Full type annotations | Task 3.2 |
| Database configuration (engine, sessionmaker, env vars) | Task 4.2 |
| Alembic initialization and env.py | Task 4.3 |
| Initial migration | Task 4.4 |
| Test fixtures (db_engine, db_session with rollback) | Task 5.1 |
| Integration test (round-trip) | Task 5.2 |

**No gaps found.**

### 2. Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No vague steps like "add appropriate error handling".
- No "similar to Task X" references.
- All code blocks contain complete, runnable code.

### 3. Type Consistency

- `Mapped[]` annotations used consistently in Task 3.2.
- `Session` type hint used in Task 5.2 test signatures.
- `Base` metadata referenced correctly in Task 4.3 (alembic/env.py) and Task 5.1 (conftest.py).
- Database URL variable names consistent: `DATABASE_URL` in config.py, used in database.py and alembic/env.py.

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-05-16-wave-1-infrastructure.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
