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
