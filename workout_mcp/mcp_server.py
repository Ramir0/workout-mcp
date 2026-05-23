"""MCP server with workout query tools."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from workout_mcp.database import SessionLocal
from workout_mcp.logging import get_logger
from workout_mcp.models import Workout, WorkoutExercise

log = get_logger(__name__)

mcp = FastMCP(
    "WorkoutServer",
    stateless_http=True,
    json_response=True,
)

# Configure MCP to serve at the mount point root (no nested /mcp path).
# Must be "/" (not "") — Starlette's Route constructor asserts path.startswith("/").
mcp.settings.streamable_http_path = "/"


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


@mcp.tool(
    title="Get Workouts by Date Range",
    description="Retrieve all workout sessions that occurred between two dates. Use this when the user asks about workouts during a specific time period, such as 'last week' or 'this month'.",
)
def get_workout_by_date_range(
    start_date: str, end_date: str
) -> list[dict[str, object]] | dict[str, str]:
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


@mcp.tool(
    title="Get Workouts by Routine",
    description="Retrieve all workouts that follow a specific routine template. Use this when the user asks about a named workout plan like 'Push Day' or 'Upper Body'.",
)
def get_workout_by_routine(routine_name: str) -> list[dict[str, object]] | dict[str, str]:
    """Retrieve all workouts for a given routine name.

    Returns full workout details including exercises and sets.
    """
    try:
        with get_db_session() as db:
            return _get_workout_by_routine(db, routine_name)
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_workout_by_routine", error=str(exc))
        return {"error": "Database query failed"}


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


@mcp.tool(
    title="Get Workouts by Exercise",
    description="Retrieve all workout sessions that include a specific exercise. Use this when the user asks about training history for a particular movement like 'Bench Press' or 'Squat'.",
)
def get_workout_by_exercise(exercise_name: str) -> list[dict[str, object]] | dict[str, str]:
    """Retrieve all workouts that contain a specific exercise.

    Returns full workout details (all exercises and sets) to preserve workout context.
    """
    try:
        with get_db_session() as db:
            return _get_workout_by_exercise(db, exercise_name)
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_workout_by_exercise", error=str(exc))
        return {"error": "Database query failed"}


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


@mcp.tool(
    title="Count Workouts",
    description="Count the total number of workouts, optionally filtered by date range or routine name. Use this when the user asks 'how many workouts' or wants to check training frequency.",
)
def get_workout_count(
    start_date: str = "",
    end_date: str = "",
    routine_name: str = "",
) -> int | dict[str, str]:
    """Get the total count of workouts, with optional filters.

    Accepts optional date range and routine name filters. Returns the integer
    count of matching workouts. Dates should be in ISO format (YYYY-MM-DD).
    """
    try:
        with get_db_session() as db:
            return _get_workout_count(db, start_date, end_date, routine_name)
    except ValueError as exc:
        log.error("invalid_parameters", tool="get_workout_count", error=str(exc))
        return {"error": f"Invalid parameters: {exc}"}
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_workout_count", error=str(exc))
        return {"error": "Database query failed"}


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


@mcp.tool(
    title="Get Last Workout",
    description="Retrieve the most recent workout session. Optionally filter by a specific exercise to find when it was last performed. Use this when the user asks 'what was my last workout' or 'when did I last do X'.",
)
def get_last_workout(exercise_name: str = "") -> dict[str, object]:
    """Get the most recent workout, optionally filtered by exercise.

    If an exercise name is provided, returns the most recent workout
    containing that exercise. Returns an empty dict if no workouts found.
    """
    try:
        with get_db_session() as db:
            return _get_last_workout(db, exercise_name)
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_last_workout", error=str(exc))
        return {"error": "Database query failed"}


def _get_max_pr_by_exercise(db: Session, exercise_name: str) -> dict[str, object]:
    """Core logic for get_max_pr_by_exercise — testable with any session."""
    from sqlalchemy import func

    from workout_mcp.models import Exercise, Set

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

    result = db.query(best_per_workout).order_by(best_per_workout.c.best_weight.desc()).first()

    if result is None:
        return {}

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


@mcp.tool(
    title="Get Max PR by Exercise",
    description="Find the heaviest single set ever recorded for an exercise. Use this when the user asks for their personal record, max weight, or heaviest lift.",
)
def get_max_pr_by_exercise(exercise_name: str) -> dict[str, object]:
    """Get the maximum personal record (heaviest best-set weight) for an exercise.

    For each workout containing this exercise, the "best set" is the single heaviest
    set. The PR is the heaviest best-set weight across all workouts.

    Args:
        exercise_name: Name of the exercise (e.g., "Bench Press").

    Returns:
        Dict with "date", "weight", and "reps" of the PR, or empty dict if no data.
    """
    try:
        with get_db_session() as db:
            return _get_max_pr_by_exercise(db, exercise_name)
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_max_pr_by_exercise", error=str(exc))
        return {"error": "Database query failed"}


def _get_min_pr_by_exercise(db: Session, exercise_name: str) -> dict[str, object]:
    """Core logic for get_min_pr_by_exercise — testable with any session."""
    from sqlalchemy import func

    from workout_mcp.models import Exercise, Set

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

    result = db.query(best_per_workout).order_by(best_per_workout.c.best_weight.asc()).first()

    if result is None:
        return {}

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


@mcp.tool(
    title="Get Min PR by Exercise",
    description="Find the lightest best-set weight recorded for an exercise. Use this when the user asks for their lightest PR or wants to see early performance data.",
)
def get_min_pr_by_exercise(exercise_name: str) -> dict[str, object]:
    """Get the minimum personal record (lightest best-set weight) for an exercise.

    For each workout containing this exercise, the "best set" is the single heaviest
    set. The PR is the lightest best-set weight across all workouts.

    Args:
        exercise_name: Name of the exercise (e.g., "Bench Press").

    Returns:
        Dict with "date", "weight", and "reps" of the PR, or empty dict if no data.
    """
    try:
        with get_db_session() as db:
            return _get_min_pr_by_exercise(db, exercise_name)
    except SQLAlchemyError as exc:
        log.error("database_error", tool="get_min_pr_by_exercise", error=str(exc))
        return {"error": "Database query failed"}
