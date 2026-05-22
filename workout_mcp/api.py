"""FastAPI application and REST API endpoints."""

from __future__ import annotations

import io
import time
import uuid
from collections.abc import Generator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from workout_mcp.database import SessionLocal
from workout_mcp.logging import get_logger
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.parser import ParseError, parse_hevy_csv

logger = get_logger(__name__)

app = FastAPI(title="Workout MCP Server")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 with field-level validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Return 409 for database constraint violations."""
    logger.error("integrity_error", error=str(exc))
    return JSONResponse(
        status_code=409,
        content={"detail": "Duplicate resource or constraint violation"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return 500 with safe message for unhandled exceptions."""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
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
                                distance_km=parsed_set.distance_km,
                                duration_seconds=parsed_set.duration_seconds,
                            )
                            db.add(set_)
                            sets_created += 1
                        else:
                            sets_discarded += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("database_import_error", error=str(exc))
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
