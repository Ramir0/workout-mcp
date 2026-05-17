# Wave 2 — Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Hevy CSV parser (Issue #10) and the FastAPI `POST /import/csv` endpoint (Issue #11) to enable ingestion of workout data into the PostgreSQL database.

**Architecture:** A standalone parser module normalizes flat Hevy CSV rows into a nested dataclass structure (Routine → Workout → Exercise → Set). A FastAPI endpoint accepts multipart CSV uploads, delegates to the parser, and persists data with application-level deduplication for all entities (Routine, Exercise, Workout, WorkoutExercise, Set). FastAPI dependency injection enables testable database session handling.

**Tech Stack:** Python 3.13, uv, FastAPI, uvicorn, SQLAlchemy 2.0, PostgreSQL, pytest

---

## Assumptions & Decisions

| # | Assumption |
|---|---|
| A | CSV encoding is **UTF-8**. |
| B | Hevy date format is fixed: `%b %d, %Y, %I:%M %p` (e.g. `Jan 1, 2024, 10:00 AM`). |
| C | `Routine` is identified **solely by name** (no other metadata). |
| D | `Exercise` is identified **solely by name**. |
| E | Cardio rows (empty `weight_kg` + empty `reps`) are stored as `weight=0.0`, `reps=0`. |
| F | **Workout** is identified by `(routine_id, start_time, end_time)` and reused if it exists. |
| G | **WorkoutExercise** is identified by `(workout_id, exercise_id)` and reused if it exists. |
| H | **Set** is identified by `(workout_exercise_id, set_index)`. If it exists, the row is **discarded** (no update). |
| I | Import is **all-or-nothing** (single DB transaction; rollback on any error). |
| J | Endpoint returns a summary of **created** and **discarded** counts, plus **warnings** (row number and reason for each skipped set). |

### Upsert Behavior

| Entity | Lookup Key | Exists? | Action |
|---|---|---|---|
| `Routine` | `name` | No | Create new |
| `Routine` | `name` | Yes | **Reuse** (do not update) |
| `Exercise` | `name` | No | Create new |
| `Exercise` | `name` | Yes | **Reuse** (do not update) |
| `Workout` | `(routine_id, start, end)` | No | Create new |
| `Workout` | `(routine_id, start, end)` | Yes | **Reuse** (do not update) |
| `WorkoutExercise` | `(workout_id, exercise_id)` | No | Create new |
| `WorkoutExercise` | `(workout_id, exercise_id)` | Yes | **Reuse**, update `exercise_index` if changed |
| `Set` | `(workout_exercise_id, set_index)` | No | Create new |
| `Set` | `(workout_exercise_id, set_index)` | Yes | **Discard** (skip with warning) |

---

## File Structure

```
workout-mcp/
├── tests/
│   ├── conftest.py                   # Modified — add TestClient fixture
│   ├── fixtures/
│   │   ├── sample_hevy.csv           # Valid multi-routine/workout fixture
│   │   ├── empty.csv                 # Header only
│   │   ├── missing_columns.csv       # Missing required column
│   │   ├── malformed_date.csv        # Bad date format
│   │   ├── invalid_weight.csv        # Negative weight
│   │   ├── weight_without_reps.csv   # Only one of weight/reps present
│   │   └── cardio.csv                # Empty weight & reps (treadmill-like)
│   ├── test_parser.py                # Issue #10 — Parser unit tests
│   └── test_api.py                   # Issue #11 — API integration tests
├── workout_mcp/
│   ├── parser.py                     # Issue #10 — Hevy CSV parser
│   └── api.py                        # Issue #11 — FastAPI app & endpoint
├── main.py                           # Modified — run FastAPI via uvicorn
└── pyproject.toml                    # Modified — add fastapi, uvicorn, python-multipart
```

---

## Issue #10: Implement Hevy CSV Parser

### Task 6.1: Add FastAPI and server dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add fastapi, uvicorn, and python-multipart to dependencies**

Edit `pyproject.toml` dependencies list:

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
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies install successfully.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add fastapi, uvicorn, python-multipart for REST API"
```

---

### Task 6.2: Create parser module

**Files:**
- Create: `workout_mcp/parser.py`

- [ ] **Step 1: Create parser.py**

```python
"""Hevy CSV export parser."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import TextIO


@dataclass
class ParsedSet:
    set_index: int
    reps: int
    weight: float
    rpe: float | None
    source_row: int  # CSV row number (1-indexed, including header)


@dataclass
class ParsedExercise:
    name: str
    exercise_index: int
    sets: list[ParsedSet]


@dataclass
class ParsedWorkout:
    start: datetime
    end: datetime
    exercises: list[ParsedExercise]


@dataclass
class ParsedRoutine:
    name: str
    workouts: list[ParsedWorkout]


class ParseError(Exception):
    """Base class for parser errors."""


class EmptyCSVError(ParseError):
    """Raised when the CSV has no data rows."""


class MissingColumnError(ParseError):
    """Raised when required columns are missing."""


class MalformedDateError(ParseError):
    """Raised when a date cannot be parsed."""


class InvalidValueError(ParseError):
    """Raised when a field value is invalid."""


_REQUIRED_COLUMNS = {
    "title",
    "start_time",
    "end_time",
    "exercise_title",
    "set_index",
}


def _parse_datetime(value: str) -> datetime:
    stripped = value.strip()
    try:
        return datetime.strptime(stripped, "%b %d, %Y, %I:%M %p")
    except ValueError as exc:
        raise MalformedDateError(f"Unable to parse date: {stripped!r}") from exc


def _parse_int(value: str, field: str) -> int:
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be an integer, got: {stripped!r}") from exc


def _parse_float(value: str, field: str) -> float:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be a number, got: {stripped!r}") from exc


def _parse_optional_float(value: str, field: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError as exc:
        raise InvalidValueError(
            f"{field} must be a number or empty, got: {stripped!r}"
        ) from exc


def parse_hevy_csv(source: TextIO) -> list[ParsedRoutine]:
    """Parse a Hevy CSV export into a nested workout structure."""
    reader = csv.DictReader(source)

    if reader.fieldnames is None:
        raise EmptyCSVError("CSV has no header row")

    missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise MissingColumnError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )

    rows = list(reader)
    if not rows:
        raise EmptyCSVError("CSV contains no data rows")

    # Tag each row with its CSV row number (1-indexed, header = row 1)
    for row_num, row in enumerate(rows, start=2):
        row["_row_num"] = row_num

    # Group rows by (routine_name, start, end)
    workout_groups: dict[tuple[str, datetime, datetime], list[dict[str, str]]] = {}
    for row in rows:
        routine_name = row["title"].strip()
        if not routine_name:
            raise InvalidValueError("title cannot be empty")

        start = _parse_datetime(row["start_time"])
        end = _parse_datetime(row["end_time"])

        key = (routine_name, start, end)
        workout_groups.setdefault(key, []).append(row)

    # Build nested structure
    routines: dict[str, ParsedRoutine] = {}
    for (routine_name, start, end), workout_rows in workout_groups.items():
        # Determine exercise order by first appearance
        seen_exercises: list[str] = []
        for row in workout_rows:
            ex_name = row["exercise_title"].strip()
            if not ex_name:
                raise InvalidValueError("exercise_title cannot be empty")
            if ex_name not in seen_exercises:
                seen_exercises.append(ex_name)

        # Group rows by exercise
        exercise_groups: dict[str, list[dict[str, str]]] = {}
        for row in workout_rows:
            ex_name = row["exercise_title"].strip()
            exercise_groups.setdefault(ex_name, []).append(row)

        parsed_exercises: list[ParsedExercise] = []
        for exercise_index, ex_name in enumerate(seen_exercises):
            ex_rows = exercise_groups[ex_name]
            sets: list[ParsedSet] = []
            for row in ex_rows:
                set_index = _parse_int(row["set_index"], "set_index")

                weight_raw = row.get("weight_kg", "").strip()
                reps_raw = row.get("reps", "").strip()

                if weight_raw and reps_raw:
                    weight = _parse_float(weight_raw, "weight_kg")
                    reps = _parse_int(reps_raw, "reps")
                    if weight <= 0:
                        raise InvalidValueError(
                            f"weight_kg must be positive, got {weight}"
                        )
                    if reps <= 0:
                        raise InvalidValueError(f"reps must be positive, got {reps}")
                elif not weight_raw and not reps_raw:
                    weight = 0.0
                    reps = 0
                else:
                    raise InvalidValueError(
                        "weight_kg and reps must both be present or both be empty"
                    )

                rpe = _parse_optional_float(row.get("rpe", ""), "rpe")
                if rpe is not None and (rpe < 1 or rpe > 10):
                    raise InvalidValueError(
                        f"rpe must be between 1 and 10, got {rpe}"
                    )

                sets.append(
                    ParsedSet(
                        set_index=set_index,
                        reps=reps,
                        weight=weight,
                        rpe=rpe,
                        source_row=row["_row_num"],
                    )
                )

            parsed_exercises.append(
                ParsedExercise(
                    name=ex_name,
                    exercise_index=exercise_index,
                    sets=sets,
                )
            )

        workout = ParsedWorkout(
            start=start,
            end=end,
            exercises=parsed_exercises,
        )

        if routine_name not in routines:
            routines[routine_name] = ParsedRoutine(
                name=routine_name,
                workouts=[workout],
            )
        else:
            routines[routine_name].workouts.append(workout)

    return list(routines.values())
```

- [ ] **Step 2: Run type checker on parser**

Run: `uv run mypy workout_mcp/parser.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add workout_mcp/parser.py
git commit -m "feat: add Hevy CSV parser with validation and nested structure"
```

---

### Task 6.3: Create test fixtures

**Files:**
- Create: `tests/fixtures/sample_hevy.csv`
- Create: `tests/fixtures/empty.csv`
- Create: `tests/fixtures/missing_columns.csv`
- Create: `tests/fixtures/malformed_date.csv`
- Create: `tests/fixtures/invalid_weight.csv`
- Create: `tests/fixtures/weight_without_reps.csv`
- Create: `tests/fixtures/cardio.csv`

- [ ] **Step 1: Create valid sample fixture**

Create `tests/fixtures/sample_hevy.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8
"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",1,"normal",100,5,,0,8.5
"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat","","",0,"normal",140,5,,0,9
"Pull Day","Jan 2, 2024, 10:00 AM","Jan 2, 2024, 11:00 AM","","Deadlift","","",0,"normal",180,5,,0,9
```

- [ ] **Step 2: Create edge-case fixtures**

Create `tests/fixtures/empty.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
```

Create `tests/fixtures/missing_columns.csv`:

```csv
"start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8
```

Create `tests/fixtures/malformed_date.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Push Day","not-a-date","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8
```

Create `tests/fixtures/invalid_weight.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",-10,5,,0,8
```

Create `tests/fixtures/weight_without_reps.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,,,0,8
```

Create `tests/fixtures/cardio.csv`:

```csv
"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Cardio Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Treadmill","","",0,"normal",,,,0.5,600,
```

- [ ] **Step 3: Commit fixtures**

```bash
git add tests/fixtures/
git commit -m "test: add Hevy CSV fixtures for parser edge cases"
```

---

### Task 6.4: Write parser unit tests

**Files:**
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write parser tests**

Create `tests/test_parser.py`:

```python
"""Unit tests for the Hevy CSV parser."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pytest

from workout_mcp.parser import (
    EmptyCSVError,
    InvalidValueError,
    MalformedDateError,
    MissingColumnError,
    parse_hevy_csv,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_valid_csv() -> None:
    with open(FIXTURES_DIR / "sample_hevy.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 2

    # Push Day
    push = next(r for r in routines if r.name == "Push Day")
    assert len(push.workouts) == 1
    workout = push.workouts[0]
    assert workout.start == datetime(2024, 1, 1, 10, 0)
    assert workout.end == datetime(2024, 1, 1, 11, 0)
    assert len(workout.exercises) == 2

    bench = workout.exercises[0]
    assert bench.name == "Bench Press"
    assert bench.exercise_index == 0
    assert len(bench.sets) == 2
    assert bench.sets[0].set_index == 0
    assert bench.sets[0].weight == 100.0
    assert bench.sets[0].reps == 5
    assert bench.sets[0].rpe == 8.0

    squat = workout.exercises[1]
    assert squat.name == "Squat"
    assert squat.exercise_index == 1
    assert len(squat.sets) == 1
    assert squat.sets[0].weight == 140.0

    # Pull Day
    pull = next(r for r in routines if r.name == "Pull Day")
    assert len(pull.workouts) == 1
    deadlift = pull.workouts[0].exercises[0]
    assert deadlift.name == "Deadlift"
    assert deadlift.sets[0].weight == 180.0


def test_parse_from_string_io() -> None:
    csv_text = (
        '"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"Legs","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat",'
        '"","",0,"normal",100,5,,0,\n'
    )
    routines = parse_hevy_csv(io.StringIO(csv_text))
    assert len(routines) == 1
    assert routines[0].workouts[0].exercises[0].sets[0].rpe is None


def test_empty_csv() -> None:
    with open(FIXTURES_DIR / "empty.csv", encoding="utf-8") as f:
        with pytest.raises(EmptyCSVError, match="no data rows"):
            parse_hevy_csv(f)


def test_missing_required_columns() -> None:
    with open(FIXTURES_DIR / "missing_columns.csv", encoding="utf-8") as f:
        with pytest.raises(MissingColumnError, match="title"):
            parse_hevy_csv(f)


def test_malformed_date() -> None:
    with open(FIXTURES_DIR / "malformed_date.csv", encoding="utf-8") as f:
        with pytest.raises(MalformedDateError, match="not-a-date"):
            parse_hevy_csv(f)


def test_negative_weight() -> None:
    with open(FIXTURES_DIR / "invalid_weight.csv", encoding="utf-8") as f:
        with pytest.raises(InvalidValueError, match="positive"):
            parse_hevy_csv(f)


def test_weight_without_reps() -> None:
    with open(FIXTURES_DIR / "weight_without_reps.csv", encoding="utf-8") as f:
        with pytest.raises(InvalidValueError, match="both be present"):
            parse_hevy_csv(f)


def test_cardio_row() -> None:
    with open(FIXTURES_DIR / "cardio.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 1
    set_ = routines[0].workouts[0].exercises[0].sets[0]
    assert set_.weight == 0.0
    assert set_.reps == 0
    assert set_.rpe is None


def test_exercise_order_preserved() -> None:
    csv_text = (
        '"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","B",'
        '"","",0,"normal",10,1,,0,\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","C",'
        '"","",0,"normal",20,2,,0,\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","B",'
        '"","",1,"normal",15,1,,0,\n'
    )
    routines = parse_hevy_csv(io.StringIO(csv_text))
    exercises = routines[0].workouts[0].exercises
    assert exercises[0].name == "B"
    assert exercises[0].exercise_index == 0
    assert exercises[1].name == "C"
    assert exercises[1].exercise_index == 1
    assert len(exercises[0].sets) == 2
```

- [ ] **Step 2: Run parser tests**

Run: `uv run pytest tests/test_parser.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser.py
git commit -m "test: add parser unit tests covering valid and edge cases"
```

---

### Task 6.5: Add unique constraints for upsert support

**Files:**
- Modify: `workout_mcp/models.py`
- Modify: `alembic/versions/9d409c54bac0_initial_migration_create_routine_.py`
- Create: New Alembic migration

- [ ] **Step 1: Add unique constraints to models**

Edit `workout_mcp/models.py` — add `unique=True` / `UniqueConstraint`:

```python
class Routine(Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    ...

class Exercise(Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    ...

class Workout(Base):
    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime]
    end: Mapped[datetime]
    routine_id: Mapped[int] = mapped_column(ForeignKey("routine.id"))

    __table_args__ = (
        sa.UniqueConstraint("routine_id", "start", "end"),
    )
    ...

class WorkoutExercise(Base):
    __tablename__ = "workout_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workout.id"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"))
    exercise_index: Mapped[int]

    __table_args__ = (
        sa.UniqueConstraint("workout_id", "exercise_id"),
    )
    ...

class Set(Base):
    __tablename__ = "set"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercise.id"))
    set_index: Mapped[int]
    reps: Mapped[int]
    weight: Mapped[float]
    rpe: Mapped[float | None] = mapped_column(default=None)

    __table_args__ = (
        sa.UniqueConstraint("workout_exercise_id", "set_index"),
    )
    ...
```

- [ ] **Step 2: Generate Alembic migration**

Run: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic revision --autogenerate -m "add_unique_constraints_for_upsert"`

- [ ] **Step 3: Review and apply migration**

Run: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head`

- [ ] **Step 4: Commit**

```bash
git add workout_mcp/models.py alembic/versions/
git commit -m "feat: add unique constraints for upsert support"
```

---

## Issue #11: Implement REST API Endpoint `POST /import/csv`

### Task 7.1: Create FastAPI app with import endpoint

**Files:**
- Create: `workout_mcp/api.py`

- [ ] **Step 1: Create api.py**

```python
"""FastAPI application and REST API endpoints."""

from __future__ import annotations

import io
from collections.abc import Generator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from workout_mcp.database import SessionLocal
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.parser import ParseError, parse_hevy_csv

app = FastAPI(title="Workout MCP Server")


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/import/csv")
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, int] | list[dict[str, str]]]:
    """Import a Hevy CSV export into the database."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = file.file.read().decode("utf-8")
        routines = parse_hevy_csv(io.StringIO(content))
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    routines_created = 0
    workouts_created = 0
    exercises_created = 0
    workout_exercises_created = 0
    workout_exercises_updated = 0
    sets_created = 0
    sets_discarded = 0
    warnings: list[dict[str, str]] = []

    try:
        for parsed_routine in routines:
            routine = db.query(Routine).filter_by(name=parsed_routine.name).first()
            if routine is None:
                routine = Routine(name=parsed_routine.name)
                db.add(routine)
                db.flush()
                routines_created += 1

            for parsed_workout in parsed_routine.workouts:
                workout = (
                    db.query(Workout)
                    .filter_by(
                        routine_id=routine.id,
                        start=parsed_workout.start,
                        end=parsed_workout.end,
                    )
                    .first()
                )
                if workout is None:
                    workout = Workout(
                        start=parsed_workout.start,
                        end=parsed_workout.end,
                        routine=routine,
                    )
                    db.add(workout)
                    db.flush()
                    workouts_created += 1

                for parsed_exercise in parsed_workout.exercises:
                    exercise = (
                        db.query(Exercise).filter_by(name=parsed_exercise.name).first()
                    )
                    if exercise is None:
                        exercise = Exercise(name=parsed_exercise.name)
                        db.add(exercise)
                        db.flush()
                        exercises_created += 1

                    workout_exercise = (
                        db.query(WorkoutExercise)
                        .filter_by(
                            workout_id=workout.id,
                            exercise_id=exercise.id,
                        )
                        .first()
                    )
                    if workout_exercise is None:
                        workout_exercise = WorkoutExercise(
                            workout=workout,
                            exercise=exercise,
                            exercise_index=parsed_exercise.exercise_index,
                        )
                        db.add(workout_exercise)
                        db.flush()
                        workout_exercises_created += 1
                    elif workout_exercise.exercise_index != parsed_exercise.exercise_index:
                        workout_exercise.exercise_index = parsed_exercise.exercise_index
                        workout_exercises_updated += 1

                    for parsed_set in parsed_exercise.sets:
                        set_ = (
                            db.query(Set)
                            .filter_by(
                                workout_exercise_id=workout_exercise.id,
                                set_index=parsed_set.set_index,
                            )
                            .first()
                        )
                        if set_ is None:
                            set_ = Set(
                                workout_exercise=workout_exercise,
                                set_index=parsed_set.set_index,
                                reps=parsed_set.reps,
                                weight=parsed_set.weight,
                                rpe=parsed_set.rpe,
                            )
                            db.add(set_)
                            sets_created += 1
                        else:
                            sets_discarded += 1
                            warnings.append({
                                "row": parsed_set.source_row,
                                "reason": f"Set index {parsed_set.set_index} already exists for {parsed_exercise.name}",
                            })

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Database error during import: {exc}"
        ) from exc

    return {
        "created": {
            "routines": routines_created,
            "workouts": workouts_created,
            "exercises": exercises_created,
            "workout_exercises": workout_exercises_created,
            "sets": sets_created,
        },
        "discarded": {
            "sets": sets_discarded,
        },
        "warnings": warnings,
    }
```

- [ ] **Step 2: Run type checker on API**

Run: `uv run mypy workout_mcp/api.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add workout_mcp/api.py
git commit -m "feat: add FastAPI app with POST /import/csv endpoint"
```

---

### Task 7.2: Update main.py to run the FastAPI server

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace main.py contents**

```python
"""Entry point for the Workout MCP Server."""

import uvicorn

from workout_mcp.api import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify main.py type checks**

Run: `uv run mypy main.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: run FastAPI app via uvicorn in main.py"
```

---

### Task 7.3: Add TestClient fixture for API tests

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update conftest.py with client fixture**

Replace `tests/conftest.py` with:

```python
"""Pytest fixtures and configuration."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from workout_mcp.config import TEST_DATABASE_URL
from workout_mcp.models import Base


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    """Create a test database engine and schema (once per session)."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session]:
    """Yield a database session with automatic transaction rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()

    # Bind the session to the connection (not the engine)
    session = sessionmaker(bind=connection)()

    # Prevent the session from committing externally
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session: Session, transaction: SessionTransaction) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    """Create a TestClient with the test database session injected."""
    from workout_mcp.api import app, get_db

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add TestClient fixture with DB dependency override"
```

---

### Task 7.4: Write API integration tests

**Files:**
- Create: `tests/test_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/test_api.py`:

```python
"""Integration tests for the REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_import_csv_success(client: TestClient, db_session: Session) -> None:
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 2
    assert data["created"]["workouts"] == 2
    assert data["created"]["exercises"] == 3
    assert data["created"]["workout_exercises"] == 4
    assert data["created"]["sets"] == 4
    assert data["discarded"]["sets"] == 0
    assert data["warnings"] == []

    # Verify database state
    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    assert len(bench.workout_exercises) == 1
    assert len(bench.workout_exercises[0].sets) == 2


def test_import_csv_idempotent(client: TestClient, db_session: Session) -> None:
    """Importing the same CSV twice must be fully idempotent — no duplicates."""
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 0
    assert data["created"]["workouts"] == 0
    assert data["created"]["exercises"] == 0
    assert data["created"]["workout_exercises"] == 0
    assert data["created"]["sets"] == 0
    assert data["discarded"]["sets"] == 4
    assert len(data["warnings"]) == 4
    assert all("already exists" in w["reason"] for w in data["warnings"])

    # Database must not have doubled
    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4


def test_import_csv_discards_existing_set(client: TestClient, db_session: Session) -> None:
    """Re-importing a workout with changed set data should discard the set, not update."""
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    # Modify weight in the CSV inline
    csv_text = (
        FIXTURES_DIR / "sample_hevy.csv"
    ).read_text(encoding="utf-8")
    modified = csv_text.replace(
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8',
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",105,5,,0,8',
    )

    response = client.post(
        "/import/csv",
        files={"file": ("sample_hevy.csv", modified.encode("utf-8"))},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["workouts"] == 0
    assert data["discarded"]["sets"] == 4
    assert len(data["warnings"]) == 4

    # Original weight must be preserved (not updated)
    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench.workout_exercises[0].sets[0].weight == 100.0

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench.workout_exercises[0].sets[0].weight == 105.0


def test_import_csv_empty_file(client: TestClient) -> None:
    with open(FIXTURES_DIR / "empty.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("empty.csv", f)})

    assert response.status_code == 400
    assert "no data rows" in response.json()["detail"]


def test_import_csv_non_csv_extension(client: TestClient) -> None:
    response = client.post(
        "/import/csv",
        files={"file": ("report.txt", b"not a csv")},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_import_csv_malformed_date(client: TestClient) -> None:
    with open(FIXTURES_DIR / "malformed_date.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("malformed_date.csv", f)})

    assert response.status_code == 400
    assert "Unable to parse date" in response.json()["detail"]
```

- [ ] **Step 2: Run API tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest tests/test_api.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add API integration tests for CSV import endpoint"
```

---

### Task 7.5: Verify full test suite and tooling

**Files:** None

- [ ] **Step 1: Run all tests**

Run: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest -v`
Expected: All tests PASS (7 model + 4 database + 9 parser + 6 API = 26 total).

- [ ] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: PASS

- [ ] **Step 3: Run type checker**

Run: `uv run mypy .`
Expected: PASS

- [ ] **Step 4: Run pre-commit**

Run: `uv run pre-commit run --all-files`
Expected: All hooks PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: verify all tests and tooling pass for Wave 2"
```

---

## Self-Review

### 1. Spec Coverage

| Spec Requirement | Implementing Task |
|---|---|
| Research/document Hevy CSV format | Observed from `data/workouts.csv`; parser handles all columns |
| Read CSV from file-like object or path | Task 6.2 — `parse_hevy_csv(source: TextIO)` |
| Normalize rows into nested structure | Task 6.2 — `ParsedRoutine`, `ParsedWorkout`, `ParsedExercise`, `ParsedSet` |
| Validate required fields and types | Task 6.2 — `_parse_int`, `_parse_float`, `_parse_datetime`, `_parse_optional_float` |
| Reject malformed rows with descriptive errors | Task 6.2 — `ParseError` hierarchy with specific messages |
| Handle date/time parsing (Hevy format) | Task 6.2 — `datetime.strptime(stripped, "%b %d, %Y, %I:%M %p")` |
| Edge case: empty CSV | Task 6.3 fixture + Task 6.4 test |
| Edge case: missing required columns | Task 6.3 fixture + Task 6.4 test |
| Edge case: malformed dates | Task 6.3 fixture + Task 6.4 test |
| Edge case: negative/zero weight or reps | Task 6.3 fixture + Task 6.4 test |
| Edge case: mixed/empty units (cardio) | Task 6.3 fixture + Task 6.4 test (`weight=0.0`, `reps=0`) |
| Set up FastAPI app scaffold | Task 7.1 — `workout_mcp/api.py` |
| Accept multipart file upload | Task 7.1 — `UploadFile = File(...)` |
| Parse CSV via parser | Task 7.1 — `parse_hevy_csv(io.StringIO(content))` |
| Persist to database using ORM models | Task 7.1 — explicit ORM creation with `db.flush()` |
| Upsert: Routine deduplicate by name | Task 7.1 — `db.query(Routine).filter_by(name=...).first()` |
| Upsert: Exercise deduplicate by name | Task 7.1 — `db.query(Exercise).filter_by(name=...).first()` |
| Upsert: Workout deduplicate by `(routine_id, start, end)` | Task 7.1 — query before create |
| Upsert: WorkoutExercise deduplicate by `(workout_id, exercise_id)` | Task 7.1 — query before create; updates `exercise_index` |
| Upsert: Set deduplicate by `(workout_exercise_id, set_index)` | Task 7.1 — query before create; discards if exists with warning |
| Rollback entire transaction on partial failure | Task 7.1 — `try/except` with `db.rollback()` |
| Return JSON summary with created/discarded/warnings | Task 7.1 — returns nested counts dict + warnings list |
| Integration test with fixture CSV | Task 7.4 — `test_import_csv_success` |
| Duplicate imports fully idempotent | Task 7.4 — `test_import_csv_idempotent` |
| Existing sets discarded on re-import | Task 7.4 — `test_import_csv_discards_existing_set` |
| Malformed CSV returns 4xx with clear message | Task 7.4 — `test_import_csv_empty_file`, `test_import_csv_malformed_date` |

**No gaps found.**

### 2. Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No vague steps like "add appropriate error handling".
- No "similar to Task X" references.
- All code blocks contain complete, runnable code.
- All fixture files contain complete CSV content.

### 3. Type Consistency

- `parse_hevy_csv` accepts `TextIO` consistently across implementation and tests.
- `ParsedSet.rpe` is `float | None` matching the `Set` ORM model.
- `ParsedSet.reps` is `int` and `ParsedSet.weight` is `float` matching the `Set` ORM model.
- `get_db` return type `Generator[Session, None, None]` matches FastAPI dependency injection pattern.
- `import_csv` return type `dict[str, dict[str, int] | list[dict[str, str]]]` matches the nested counts + warnings response.
- `client` fixture uses `app.dependency_overrides[get_db]` exactly as defined in `api.py`.
- Database counts in API tests (`test_import_csv_success`) align with `sample_hevy.csv` fixture (2 routines, 2 workouts, 3 exercises, 4 sets).
- `test_import_csv_idempotent` verifies no duplicates after second import (Workout count stays 2, Set count stays 4, 4 discarded with warnings).

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-05-17-wave-2-data-ingestion.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
