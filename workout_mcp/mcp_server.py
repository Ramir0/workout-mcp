"""MCP server with workout query tools."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session, joinedload

from workout_mcp.database import SessionLocal
from workout_mcp.models import Workout, WorkoutExercise

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


def _serialize_workout(workout: Workout) -> dict[str, object]:
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


def _get_workout_by_date_range(
    db: Session, start_date: str, end_date: str
) -> list[dict[str, object]]:
    """Core logic for get_workout_by_date_range — testable with any session."""
    from sqlalchemy import select

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    stmt = (
        select(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.sets),
        )
        .filter(Workout.start >= start, Workout.start <= end)
        .order_by(Workout.start)
    )
    workouts = db.execute(stmt).unique().scalars().all()
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_date_range(start_date: str, end_date: str) -> list[dict[str, object]]:
    """Retrieve all workouts within a date range.

    Returns full workout details including routine name, exercises, and sets.
    Dates should be in ISO format (YYYY-MM-DD).
    """
    with get_db_session() as db:
        return _get_workout_by_date_range(db, start_date, end_date)


def _get_workout_by_routine(db: Session, routine_name: str) -> list[dict[str, object]]:
    """Core logic for get_workout_by_routine — testable with any session."""
    from sqlalchemy import select

    from workout_mcp.models import Routine

    stmt = (
        select(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.sets),
        )
        .join(Workout.routine)
        .filter(Routine.name == routine_name)
        .order_by(Workout.start)
    )
    workouts = db.execute(stmt).unique().scalars().all()
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_routine(routine_name: str) -> list[dict[str, object]]:
    """Retrieve all workouts for a given routine name.

    Returns full workout details including exercises and sets.
    """
    with get_db_session() as db:
        return _get_workout_by_routine(db, routine_name)


def _get_workout_by_exercise(db: Session, exercise_name: str) -> list[dict[str, object]]:
    """Core logic for get_workout_by_exercise — testable with any session."""
    from sqlalchemy import select

    from workout_mcp.models import Exercise

    stmt = (
        select(Workout)
        .options(
            joinedload(Workout.routine),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.exercise),
            joinedload(Workout.workout_exercises).joinedload(WorkoutExercise.sets),
        )
        .join(Workout.workout_exercises)
        .join(WorkoutExercise.exercise)
        .filter(Exercise.name == exercise_name)
        .order_by(Workout.start)
    )
    workouts = db.execute(stmt).unique().scalars().all()
    return [_serialize_workout(w) for w in workouts]


@mcp.tool()
def get_workout_by_exercise(exercise_name: str) -> list[dict[str, object]]:
    """Retrieve all workouts that contain a specific exercise.

    Returns full workout details (all exercises and sets) to preserve workout context.
    """
    with get_db_session() as db:
        return _get_workout_by_exercise(db, exercise_name)


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
