"""Database sync service for Hevy API data."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workout_mcp.hevy_mapper import map_hevy_workout_to_models
from workout_mcp.logging import get_logger
from workout_mcp.models import Exercise, Routine, Workout

logger = get_logger(__name__)


def upsert_hevy_workout(db: Session, hevy_data: dict[str, Any]) -> None:
    """Upsert a Hevy workout into the database.

    Uses existing unique constraints:
    - Routine by name
    - Workout by (routine_id, start, end) — delete and replace on conflict
    - Exercise by name
    """
    routine_model, workout_model, exercises, workout_exercises, sets = map_hevy_workout_to_models(
        hevy_data
    )

    # Upsert routine by name
    routine = db.query(Routine).filter_by(name=routine_model.name).first()
    if routine is None:
        routine = Routine(name=routine_model.name)
        db.add(routine)
        db.flush()
        logger.info("routine_created", name=routine.name)

    # Check for existing workout by unique constraint
    existing_workout = (
        db.query(Workout)
        .filter_by(
            routine_id=routine.id,
            start=workout_model.start,
            end=workout_model.end,
        )
        .first()
    )

    if existing_workout is not None:
        db.delete(existing_workout)
        db.flush()
        logger.info(
            "workout_deleted_for_update",
            routine=routine.name,
            start=workout_model.start.isoformat(),
        )

    # Upsert exercises by name BEFORE adding workout, to avoid unique
    # constraint violations when mapper creates duplicate transient exercises.
    for exercise_model in exercises:
        exercise = db.query(Exercise).filter_by(name=exercise_model.name).first()
        if exercise is None:
            exercise = Exercise(name=exercise_model.name)
            db.add(exercise)
            db.flush()
            logger.info("exercise_created", name=exercise.name)

    # Update workout_exercise references to use the persisted exercise instances
    for we in workout_exercises:
        exercise_name = we.exercise.name
        persisted_exercise = db.query(Exercise).filter_by(name=exercise_name).first()
        assert persisted_exercise is not None
        we.exercise = persisted_exercise

    # Now wire the workout to the persisted routine and add it.  Cascade on
    # ``Workout.workout_exercises`` and ``WorkoutExercise.sets`` will insert
    # the related rows automatically.
    workout_model.routine = routine
    db.add(workout_model)
    db.flush()

    logger.info(
        "workout_upserted",
        title=workout_model.title,
        routine=routine.name,
        exercises=len(exercises),
        sets=len(sets),
    )
