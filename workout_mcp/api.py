"""FastAPI application and REST API endpoints."""

from __future__ import annotations

import io
import logging
from collections.abc import Generator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workout_mcp.database import SessionLocal
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.parser import ParseError, parse_hevy_csv

logger = logging.getLogger(__name__)

app = FastAPI(title="Workout MCP Server")


def get_db() -> Generator[Session]:
    """Yield a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/import/csv")
def import_csv(
    file: UploadFile = File(...),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, dict[str, int] | list[dict[str, str]]]:
    """Import a Hevy CSV export into the database."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = file.file.read().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded") from exc

    try:
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
                    exercise = db.query(Exercise).filter_by(name=parsed_exercise.name).first()
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
                            warnings.append(
                                {
                                    "row": str(parsed_set.source_row),
                                    "reason": f"Set index {parsed_set.set_index} already exists for {parsed_exercise.name}",
                                }
                            )

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error during CSV import")
        raise HTTPException(status_code=500, detail="Database error during import") from exc

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
