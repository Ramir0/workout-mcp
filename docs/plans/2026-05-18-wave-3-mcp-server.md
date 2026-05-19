# Wave 3 — MCP Server & Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the MCP server scaffold (Issue #12), all 7 MCP tools (Issues #9–#11), and Dockerize the application for deployment.

**Architecture:** The MCP server is built with `FastMCP` using streamable HTTP transport (stateless mode). It is mounted as a sub-application on the existing FastAPI app at `/mcp`. The FastAPI app continues serving REST endpoints (e.g., `POST /import/csv`) at its root. The application runs in a Docker container exposing port 8000; the host's existing HTTP server handles reverse proxying and TLS termination. MCP tools are plain Python functions decorated with `@mcp.tool()` that use synchronous SQLAlchemy sessions to query PostgreSQL.

**Tech Stack:** Python 3.13, uv, FastMCP (from `mcp[cli]`), FastAPI, SQLAlchemy 2.0 (sync), PostgreSQL, Docker, Docker Compose, pytest

---

## Assumptions & Decisions

| # | Assumption |
|---|---|
| A | MCP transport is **streamable HTTP** (not stdio) — required for remote access via subdomain. |
| B | MCP server runs in **stateless mode** (`stateless_http=True`) — no session persistence between tool calls. Simpler, more scalable. |
| C | MCP server is **mounted on FastAPI** at `/mcp` — single process, single port (8000). |
| D | Production deployment uses a **separate `docker-compose.prod.yml`** — local dev `docker-compose.yml` (PostgreSQL only) is unchanged. |
| E | MCP tools use **sync SQLAlchemy sessions** (consistent with existing API code). Each tool call opens and closes its own session. |
| F | MCP tools return **JSON-serializable dicts/lists** — not Pydantic models. AI agents interpret structured data. |
| G | PR (personal record) tools use **weight-only** PRs (not volume). "Best set" = heaviest set per workout for that exercise. |
| H | `get_workout_by_*` tools return **full workout details** (all exercises and sets) to preserve workout context for AI agents. |
| I | The host's existing HTTP server handles reverse proxying and TLS. The container is **subdomain-agnostic** — it just exposes port 8000. |

---

## File Structure

```
workout-mcp/
├── .dockerignore                         # NEW — exclude .git, .venv, tests, etc.
├── Dockerfile                            # NEW — Docker build
├── docker-compose.prod.yml               # NEW — production: app + postgres
├── docker-compose.yml                    # EXISTING — local dev (unchanged)
├── main.py                               # MODIFY — mount MCP on FastAPI
├── workout_mcp/
│   ├── mcp_server.py                     # NEW — FastMCP server + 7 tool functions
│   └── (existing files unchanged)
├── tests/
│   ├── test_mcp_tools.py                 # NEW — MCP tool integration tests
│   └── (existing files unchanged)
├── .env.example                          # MODIFY — add production vars
└── README.md                             # MODIFY — update MCP config, Docker docs
```

---

## Issue #12: Set Up MCP Server Scaffold

### Task 12.1: Create FastMCP server module

**Files:**
- Create: `workout_mcp/mcp_server.py`

- [x] **Step 1: Create mcp_server.py with FastMCP setup and DB session helper**

```python
"""MCP server with workout query tools."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from workout_mcp.database import SessionLocal
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise

mcp = FastMCP(
    "WorkoutServer",
    stateless_http=True,
    json_response=True,
)


@contextmanager
def get_db_session() -> Generator[Session]:
    """Yield a database session, closing it on exit."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [x] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/mcp_server.py`
Expected: PASS

- [x] **Step 3: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add FastMCP server scaffold with DB session helper"
```

---

### Task 12.2: Mount MCP server on FastAPI

**Files:**
- Modify: `main.py`

- [x] **Step 1: Update main.py to mount MCP on FastAPI with lifespan**

Replace `main.py` with:

```python
"""Entry point for the Workout MCP Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from starlette.routing import Mount

from workout_mcp.api import app
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
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Verify FastAPI still starts (no tools yet, but mount should work)**

Run: `python main.py` (Ctrl+C after confirming startup)
Expected: Server starts on port 8000 without errors.

- [x] **Step 3: Run type checker**

Run: `uv run mypy main.py`
Expected: PASS

- [x] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: mount MCP server on FastAPI at /mcp with lifespan"
```

---

## Issue #13: Implement Workout Retrieval MCP Tools

### Task 13.1: Implement get_workout_by_date_range tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_workout_by_date_range to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _serialize_workout(workout: Workout) -> dict:
    """Serialize a Workout ORM object to a JSON-compatible dict."""
    return {
        "id": workout.id,
        "start": workout.start.isoformat(),
        "end": workout.end.isoformat(),
        "routine": workout.routine.name,
        "exercises": [
            {
                "name": we.exercise.name,
                "exercise_index": we.exercise_index,
                "sets": [
                    {
                        "set_index": s.set_index,
                        "weight": s.weight,
                        "reps": s.reps,
                        "rpe": s.rpe,
                    }
                    for s in we.sets
                ],
            }
            for we in sorted(workout.workout_exercises, key=lambda w: w.exercise_index)
        ],
    }


def _get_workout_by_date_range(db: Session, start_date: str, end_date: str) -> list[dict]:
    """Core logic for get_workout_by_date_range — testable with any session."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    workouts = (
        db.query(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.sets),
        )
        .filter(Workout.start >= start, Workout.start <= end)
        .order_by(Workout.start)
        .unique()
        .all()
    )
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_date_range(start_date: str, end_date: str) -> list[dict]:
    """Retrieve all workouts within a date range.

    Returns full workout details including routine name, exercises, and sets.
    Dates should be in ISO format (YYYY-MM-DD).
    """
    with get_db_session() as db:
        return _get_workout_by_date_range(db, start_date, end_date)
```

- [x] **Step 2: Run type checker**

Run: `uv run mypy workout_mcp/mcp_server.py`
Expected: PASS

- [x] **Step 3: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_workout_by_date_range MCP tool"
```

---

### Task 13.2: Implement get_workout_by_routine tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_workout_by_routine to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_workout_by_routine(db: Session, routine_name: str) -> list[dict]:
    """Core logic for get_workout_by_routine — testable with any session."""
    workouts = (
        db.query(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.sets),
        )
        .join(Routine)
        .filter(Routine.name == routine_name)
        .order_by(Workout.start)
        .unique()
        .all()
    )
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_routine(routine_name: str) -> list[dict]:
    """Retrieve all workouts for a given routine name.

    Returns full workout details including exercises and sets.
    """
    with get_db_session() as db:
        return _get_workout_by_routine(db, routine_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_workout_by_routine MCP tool"
```

---

### Task 13.3: Implement get_workout_by_exercise tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_workout_by_exercise to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_workout_by_exercise(db: Session, exercise_name: str) -> list[dict]:
    """Core logic for get_workout_by_exercise — testable with any session."""
    workouts = (
        db.query(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises)
            .joinedload(WorkoutExercise.sets),
        )
        .join(Workout.workout_exercises)
        .join(WorkoutExercise.exercise)
        .filter(Exercise.name == exercise_name)
        .order_by(Workout.start)
        .unique()
        .all()
    )
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_exercise(exercise_name: str) -> list[dict]:
    """Retrieve all workouts that contain a specific exercise.

    Returns full workout details (all exercises and sets) to preserve workout context.
    """
    with get_db_session() as db:
        return _get_workout_by_exercise(db, exercise_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_workout_by_exercise MCP tool"
```

---

## Issue #14: Implement Workout Count and Last-Workout MCP Tools

### Task 14.1: Implement get_workout_count tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_workout_count to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_workout_count(
    db: Session,
    start_date: str = "",
    end_date: str = "",
    routine_name: str = "",
) -> int:
    """Core logic for get_workout_count — testable with any session."""
    from sqlalchemy import func, select

    from workout_mcp.models import Routine

    stmt = select(func.count()).select_from(Workout)

    if start_date:
        stmt = stmt.filter(Workout.start >= datetime.fromisoformat(start_date))
    if end_date:
        end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
        stmt = stmt.filter(Workout.start <= end)
    if routine_name:
        stmt = stmt.join(Workout.routine).filter(Routine.name == routine_name)

    return db.execute(stmt).scalar() or 0


@mcp.tool()
def get_workout_count(
    start_date: str = "",
    end_date: str = "",
    routine_name: str = "",
) -> int:
    """Get the total count of workouts, with optional filters.

    Accepts optional date range and routine name filters. Returns the integer
    count of matching workouts. Dates should be in ISO format (YYYY-MM-DD).
    """
    with get_db_session() as db:
        return _get_workout_count(db, start_date, end_date, routine_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_workout_count MCP tool"
```

---

### Task 14.2: Implement get_last_workout tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_last_workout to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_last_workout(db: Session, exercise_name: str = "") -> dict[str, object]:
    """Core logic for get_last_workout — testable with any session."""
    from sqlalchemy import select

    from workout_mcp.models import Exercise

    stmt = (
        select(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.sets),
        )
        .order_by(Workout.start.desc())
    )

    if exercise_name:
        stmt = (
            stmt.join(Workout.workout_exercises)
            .join(WorkoutExercise.exercise)
            .filter(Exercise.name == exercise_name)
        )

    workout = db.execute(stmt).unique().scalars().first()
    if workout is None:
        return {}
    return _serialize_workout(workout)


@mcp.tool()
def get_last_workout(exercise_name: str = "") -> dict[str, object]:
    """Get the most recent workout, optionally filtered by exercise.

    If an exercise name is provided, returns the most recent workout
    containing that exercise. Returns an empty dict if no workouts found.
    """
    with get_db_session() as db:
        return _get_last_workout(db, exercise_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_last_workout MCP tool"
```

---

## Issue #15: Implement Personal Record MCP Tools

### Task 15.1: Implement get_max_pr_by_exercise tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_max_pr_by_exercise to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_max_pr_by_exercise(db: Session, exercise_name: str) -> dict:
    """Core logic for get_max_pr_by_exercise — testable with any session."""
    # Subquery: max weight per workout for this exercise
    best_per_workout = (
        db.query(
            Workout.start.label("workout_start"),
            func.max(Set.weight).label("best_weight"),
        )
        .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
        .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
        .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
        .filter(Exercise.name == exercise_name)
        .group_by(Workout.id, Workout.start)
        .subquery()
    )

    # Find the overall max
    result = (
        db.query(best_per_workout)
        .order_by(best_per_workout.c.best_weight.desc())
        .first()
    )

    if result is None:
        return {}

    # Get the full set details for the PR workout
    pr_workout_start = result.workout_start
    pr_weight = result.best_weight

    pr_set = (
        db.query(Set)
        .join(WorkoutExercise, WorkoutExercise.id == Set.workout_exercise_id)
        .join(Workout, Workout.id == WorkoutExercise.workout_id)
        .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
        .filter(
            Exercise.name == exercise_name,
            Workout.start == pr_workout_start,
            Set.weight == pr_weight,
        )
        .order_by(Set.reps.desc())
        .first()
    )

    if pr_set is None:
        return {}

    return {
        "date": pr_workout_start.isoformat(),
        "weight": pr_set.weight,
        "reps": pr_set.reps,
    }


@mcp.tool()
def get_max_pr_by_exercise(exercise_name: str) -> dict:
    """Get the maximum personal record (heaviest best-set weight) for an exercise.

    For each workout containing this exercise, the "best set" is the single heaviest
    set. The PR is the heaviest best-set weight across all workouts.

    Args:
        exercise_name: Name of the exercise (e.g., "Bench Press").

    Returns:
        Dict with "date", "weight", and "reps" of the PR, or empty dict if no data.
    """
    with get_db_session() as db:
        return _get_max_pr_by_exercise(db, exercise_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_max_pr_by_exercise MCP tool"
```

---

### Task 15.2: Implement get_min_pr_by_exercise tool

**Files:**
- Modify: `workout_mcp/mcp_server.py`

- [x] **Step 1: Add get_min_pr_by_exercise to mcp_server.py**

Append to `workout_mcp/mcp_server.py`:

```python
def _get_min_pr_by_exercise(db: Session, exercise_name: str) -> dict:
    """Core logic for get_min_pr_by_exercise — testable with any session."""
    # Subquery: max weight per workout for this exercise
    best_per_workout = (
        db.query(
            Workout.start.label("workout_start"),
            func.max(Set.weight).label("best_weight"),
        )
        .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
        .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
        .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
        .filter(Exercise.name == exercise_name)
        .group_by(Workout.id, Workout.start)
        .subquery()
    )

    # Find the overall min
    result = (
        db.query(best_per_workout)
        .order_by(best_per_workout.c.best_weight.asc())
        .first()
    )

    if result is None:
        return {}

    # Get the full set details for the PR workout
    pr_workout_start = result.workout_start
    pr_weight = result.best_weight

    pr_set = (
        db.query(Set)
        .join(WorkoutExercise, WorkoutExercise.id == Set.workout_exercise_id)
        .join(Workout, Workout.id == WorkoutExercise.workout_id)
        .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
        .filter(
            Exercise.name == exercise_name,
            Workout.start == pr_workout_start,
            Set.weight == pr_weight,
        )
        .order_by(Set.reps.desc())
        .first()
    )

    if pr_set is None:
        return {}

    return {
        "date": pr_workout_start.isoformat(),
        "weight": pr_set.weight,
        "reps": pr_set.reps,
    }


@mcp.tool()
def get_min_pr_by_exercise(exercise_name: str) -> dict:
    """Get the minimum personal record (lightest best-set weight) for an exercise.

    For each workout containing this exercise, the "best set" is the single heaviest
    set. The PR is the lightest best-set weight across all workouts.

    Args:
        exercise_name: Name of the exercise (e.g., "Bench Press").

    Returns:
        Dict with "date", "weight", and "reps" of the PR, or empty dict if no data.
    """
    with get_db_session() as db:
        return _get_min_pr_by_exercise(db, exercise_name)
```

- [x] **Step 2: Commit**

```bash
git add workout_mcp/mcp_server.py
git commit -m "feat: add get_min_pr_by_exercise MCP tool"
```

---

## Testing

### Task 16.1: Write MCP tool integration tests

**Files:**
- Create: `tests/test_mcp_tools.py`

- [x] **Step 1: Create test file with fixtures and all tool tests**

Create `tests/test_mcp_tools.py`:

```python
"""Integration tests for MCP tools."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.mcp_server import (
    _get_last_workout,
    _get_max_pr_by_exercise,
    _get_min_pr_by_exercise,
    _get_workout_by_date_range,
    _get_workout_by_exercise,
    _get_workout_by_routine,
    _get_workout_count,
)


def _seed_workouts(db: Session) -> None:
    """Seed test data: Push Day (Jan 1), Pull Day (Jan 2), Push Day (Jan 3)."""
    push_routine = Routine(name="Push Day")
    pull_routine = Routine(name="Pull Day")
    db.add_all([push_routine, pull_routine])
    db.flush()

    push_workout_1 = Workout(
        start=datetime(2024, 1, 1, 10, 0),
        end=datetime(2024, 1, 1, 11, 0),
        routine=push_routine,
    )
    pull_workout = Workout(
        start=datetime(2024, 1, 2, 10, 0),
        end=datetime(2024, 1, 2, 11, 0),
        routine=pull_routine,
    )
    push_workout_2 = Workout(
        start=datetime(2024, 1, 3, 10, 0),
        end=datetime(2024, 1, 3, 11, 0),
        routine=push_routine,
    )
    db.add_all([push_workout_1, pull_workout, push_workout_2])
    db.flush()

    bench = Exercise(name="Bench Press")
    squat = Exercise(name="Squat")
    deadlift = Exercise(name="Deadlift")
    db.add_all([bench, squat, deadlift])
    db.flush()

    we_bench_1 = WorkoutExercise(
        workout=push_workout_1, exercise=bench, exercise_index=0
    )
    we_squat = WorkoutExercise(
        workout=push_workout_1, exercise=squat, exercise_index=1
    )
    we_deadlift = WorkoutExercise(
        workout=pull_workout, exercise=deadlift, exercise_index=0
    )
    we_bench_2 = WorkoutExercise(
        workout=push_workout_2, exercise=bench, exercise_index=0
    )
    db.add_all([we_bench_1, we_squat, we_deadlift, we_bench_2])
    db.flush()

    sets = [
        Set(workout_exercise=we_bench_1, set_index=0, reps=5, weight=80.0, rpe=7.0),
        Set(workout_exercise=we_bench_1, set_index=1, reps=5, weight=100.0, rpe=8.5),
        Set(workout_exercise=we_squat, set_index=0, reps=5, weight=140.0, rpe=9.0),
        Set(workout_exercise=we_deadlift, set_index=0, reps=5, weight=180.0, rpe=9.0),
        Set(workout_exercise=we_bench_2, set_index=0, reps=3, weight=120.0, rpe=9.5),
    ]
    db.add_all(sets)
    db.commit()


def test_get_workout_by_date_range(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_date_range(db_session, "2024-01-01", "2024-01-01")
    assert len(results) == 1
    assert results[0]["routine"] == "Push Day"
    assert len(results[0]["exercises"]) == 2


def test_get_workout_by_date_range_full_month(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_date_range(db_session, "2024-01-01", "2024-01-31")
    assert len(results) == 3


def test_get_workout_by_date_range_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_date_range(db_session, "2025-01-01", "2025-01-31")
    assert results == []


def test_get_workout_by_routine(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_routine(db_session, "Push Day")
    assert len(results) == 2
    assert results[0]["routine"] == "Push Day"
    exercise_names = [e["name"] for e in results[0]["exercises"]]
    assert "Bench Press" in exercise_names
    assert "Squat" in exercise_names


def test_get_workout_by_routine_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_routine(db_session, "Nonexistent")
    assert results == []


def test_get_workout_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_exercise(db_session, "Bench Press")
    assert len(results) == 2
    assert results[0]["routine"] == "Push Day"
    # Should include ALL exercises for the workout, not just Bench Press
    assert len(results[0]["exercises"]) == 2


def test_get_workout_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    results = _get_workout_by_exercise(db_session, "Curls")
    assert results == []


def test_get_workout_count(db_session: Session) -> None:
    _seed_workouts(db_session)
    assert _get_workout_count(db_session) == 3
    assert _get_workout_count(db_session, routine_name="Push Day") == 2
    assert _get_workout_count(db_session, start_date="2024-01-02", end_date="2024-01-02") == 1
    assert _get_workout_count(db_session, routine_name="Nonexistent") == 0


def test_get_last_workout(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_last_workout(db_session)
    assert result["routine"] == "Push Day"
    assert result["start"] == "2024-01-03T10:00:00"


def test_get_last_workout_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_last_workout(db_session, exercise_name="Bench Press")
    assert result["routine"] == "Push Day"
    assert result["start"] == "2024-01-03T10:00:00"


def test_get_last_workout_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_last_workout(db_session, exercise_name="Nonexistent")
    assert result == {}


def test_get_max_pr_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_max_pr_by_exercise(db_session, "Bench Press")
    assert result["weight"] == 120.0
    assert result["reps"] == 3
    assert "2024-01-03" in result["date"]


def test_get_max_pr_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_max_pr_by_exercise(db_session, "Nonexistent")
    assert result == {}


def test_get_min_pr_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_min_pr_by_exercise(db_session, "Bench Press")
    assert result["weight"] == 100.0
    assert result["reps"] == 5
    assert "2024-01-01" in result["date"]


def test_get_min_pr_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    result = _get_min_pr_by_exercise(db_session, "Nonexistent")
    assert result == {}
```

- [x] **Step 2: Run MCP tool tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_mcp_tools.py -v`
Expected: All 17 tests PASS.

- [x] **Step 3: Commit**

```bash
git add tests/test_mcp_tools.py
git commit -m "test: add MCP tool integration tests for all 7 tools"
```

---

## Docker & Deployment

### Task 17.1: Create Dockerfile and .dockerignore

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [x] **Step 1: Create .dockerignore**

Create `.dockerignore`:

```
.git
.venv
__pycache__
*.pyc
.env
data/
tests/
.pytest_cache
.mypy_cache
.ruff_cache
*.egg-info
dist/
build/
```

- [x] **Step 2: Create multi-stage Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.13-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic/ alembic.ini ./
COPY . .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [x] **Step 3: Test Docker build**

Run: `docker build -t workout-mcp .`
Expected: Build succeeds.

- [x] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add Dockerfile and .dockerignore for production container"
```


---

### Task 17.2: Create production docker-compose

**Files:**
- Create: `docker-compose.prod.yml`

- [x] **Step 1: Create production compose file**

Create `docker-compose.prod.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: workout_mcp
      POSTGRES_USER: ${DATABASE_USER:-postgres}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-h", "localhost", "-p", "5432"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  app:
    build: .
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      DATABASE_URL: postgresql://${DATABASE_USER:-postgres}:${DATABASE_PASSWORD:-postgres}@postgres:5432/workout_mcp
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
```

- [x] **Step 2: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: add production docker-compose with app and postgres"
```

---

### Task 17.3: Update .env.example

**Files:**
- Modify: `.env.example`

- [x] **Step 1: Add production variables**

Replace `.env.example` with:

```env
# Local development
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_URL=postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@localhost:5432/workout_mcp
TEST_DATABASE_URL=postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@localhost:5432/workout_mcp_test

# Production (docker-compose.prod.yml)
APP_PORT=8000
```

- [x] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add APP_PORT to .env.example"
```

---

## Issue #14: Documentation

### Task 18.1: Update README with MCP and Docker deployment docs

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update README MCP Configuration section**

Replace the "### MCP Configuration" section with:

```markdown
### MCP Configuration

Connect to the server at `https://workout.amir-aranibar.com`:

```json
{
  "mcpServers": {
    "workout": {
      "url": "https://workout.amir-aranibar.com/mcp"
    }
  }
}
```

#### Example Queries

Once connected, you can ask your AI agent:

- "Show me all chest workouts from last month"
- "What's my heaviest squat this year?"
- "How many workouts did I do this week?"
- "When was the last time I did deadlifts?"
- "What's my bench press PR?"
```

- [x] **Step 2: Add Docker Deployment section**

Add before the "Development" section:

```markdown
## Docker Deployment

### Production

1. Set environment variables:
```bash
export DATABASE_USER=postgres
export DATABASE_PASSWORD=<secure-password>
```

2. Run migrations:
```bash
docker compose -f docker-compose.prod.yml run --rm app uv run alembic upgrade head
```

3. Start all services:
```bash
docker compose -f docker-compose.prod.yml up -d
```

4. Verify: `curl http://localhost:8000/mcp`

The host's HTTP server should reverse proxy to `localhost:8000`.

### Local Development

```bash
docker-compose up -d          # Start PostgreSQL
python main.py                # Start server (REST API + MCP)
```
```

- [x] **Step 3: Add MCP Tools reference table**

Add after the existing "MCP Tools for AI Agents" table:

```markdown
#### Tool Details

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_workout_by_date_range` | `start_date: str`, `end_date: str` (ISO format) | List of workouts with exercises and sets |
| `get_workout_by_routine` | `routine_name: str` | List of workouts for that routine |
| `get_workout_by_exercise` | `exercise_name: str` | List of workouts containing that exercise |
| `get_workout_count` | `start_date?`, `end_date?`, `routine_name?` | Integer count |
| `get_last_workout` | `exercise_name?` | Most recent workout (or empty dict) |
| `get_max_pr_by_exercise` | `exercise_name: str` | `{date, weight, reps}` or empty dict |
| `get_min_pr_by_exercise` | `exercise_name: str` | `{date, weight, reps}` or empty dict |
```

- [x] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README with MCP remote config, Docker deployment, and tool reference"
```

---

## Verification

### Task 19.1: Run full test suite and tooling

**Files:** None

- [x] **Step 1: Run all tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest -v`
Expected: All tests PASS (7 model + 4 database + 10 parser + 6 API + 17 MCP tools = 44 total).

- [x] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: PASS

- [x] **Step 3: Run type checker**

Run: `uv run mypy .`
Expected: PASS

- [x] **Step 4: Run pre-commit**

Run: `uv run pre-commit run --all-files`
Expected: All hooks PASS

- [x] **Step 5: Commit**

```bash
git commit -m "chore: verify all tests and tooling pass for Wave 3"
```

---

## Self-Review

### 1. Spec Coverage

| Spec Requirement (Roadmap) | Implementing Task |
|---|---|
| **Issue #12: MCP server scaffold** | |
| Integrate FastMCP into the application | Task 12.1 — `workout_mcp/mcp_server.py` |
| Configure MCP for streamable HTTP transport | Task 12.1 — `stateless_http=True, json_response=True` |
| Server lifecycle (startup/shutdown) | Task 12.2 — lifespan context manager with `mcp.session_manager.run()` |
| Mount MCP alongside FastAPI | Task 12.2 — `Mount("/mcp", app=mcp.streamable_http_app())` |
| Docker container deployment | Tasks 17.1–17.2 |
| Expose via host reverse proxy | Task 17.2 — container exposes port 8000, host handles TLS |
| **Issue #13: Workout retrieval tools** | |
| `get_workout_by_date_range(start_date, end_date)` | Task 13.1 |
| `get_workout_by_routine(routine_name)` | Task 13.2 |
| `get_workout_by_exercise(exercise_name)` | Task 13.3 |
| Proper `@mcp.tool()` decorators | Tasks 13.1–13.3 |
| Typed parameters and return types | Tasks 13.1–13.3 |
| Error handling for empty results (empty list, not error) | Tasks 13.1–13.3 |
| **Issue #14: Count and last-workout tools** | |
| `get_workout_count(start_date?, end_date?, routine_name?)` | Task 14.1 |
| `get_last_workout(exercise_name?)` | Task 14.2 |
| **Issue #15: PR tools** | |
| `get_min_pr_by_exercise(exercise_name)` | Task 15.2 |
| `get_max_pr_by_exercise(exercise_name)` | Task 15.1 |
| "Best set" = heaviest set per workout | Tasks 15.1–15.2 — `func.max(Set.weight)` grouped by workout |
| Return `{date, weight, reps}` | Tasks 15.1–15.2 |
| **Testing** | |
| Unit tests per tool with fixture data | Task 16.1 — 15 tests covering all 7 tools |
| **Documentation** | |
| MCP client configuration examples | Task 18.1 |
| MCP tool usage examples | Task 18.1 — example queries in README |
| Docker deployment instructions | Task 18.1 |

**No gaps found.**

### 2. Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No vague steps like "add appropriate error handling".
- No "similar to Task X" references.
- All code blocks contain complete, runnable code.

### 3. Type Consistency

- `_serialize_workout` returns `dict` matching the structure described in README query examples.
- `get_db_session()` yields `Session` consistent with `SessionLocal` in `database.py`.
- MCP tool parameter types (`str`) match the README tool signatures.
- PR tool return type `dict` with `date`, `weight`, `reps` keys matches roadmap spec.
- `mcp_server.py` imports (`Routine`, `Workout`, etc.) match existing `models.py`.
- `main.py` lifespan type matches Starlette's expected `asynccontextmanager` signature.
- `docker-compose.prod.yml` exposes port 8000 and `DATABASE_URL` format matches `config.py` expectations.
- Each MCP tool has a `_` prefixed core function (e.g., `_get_workout_by_date_range`) that accepts `db: Session` for testability. The `@mcp.tool()` wrapper handles session lifecycle.

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-05-18-wave-3-mcp-server.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
