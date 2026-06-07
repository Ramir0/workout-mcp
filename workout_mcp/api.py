"""FastAPI application and REST API endpoints."""

from __future__ import annotations

import io
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from workout_mcp.config import settings
from workout_mcp.database import SessionLocal
from workout_mcp.hevy_client import HevyAPIError, HevyClient
from workout_mcp.logging import get_logger
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.parser import ParseError, parse_hevy_csv
from workout_mcp.sync import SyncMode, trigger_sync
from workout_mcp.sync_service import upsert_hevy_workout

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield


app = FastAPI(title="Workout MCP Server", lifespan=lifespan)


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

if settings.cors_origins:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_db() -> Generator[Session]:
    """Yield a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/import/csv")
async def import_csv(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, dict[str, int]]:
    """Import a Hevy CSV export into the database."""
    content_type = request.headers.get("content-type", "")
    if "csv" not in content_type:
        raise HTTPException(status_code=400, detail="Content-Type must be text/csv")

    body = await request.body()
    try:
        content = body.decode("utf-8")
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
    sets_created = 0
    sets_discarded = 0

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
                else:
                    # Re-import path: clear stale WorkoutExercise rows (and
                    # their Set children, via ORM cascade) so the upsert below
                    # produces exactly the new layout. Use ORM-level delete so
                    # the cascade fires; a bulk query.delete() would bypass it
                    # and trip the FK from set.workout_exercise_id.
                    stale_workout_exercises = (
                        db.query(WorkoutExercise).filter_by(workout_id=workout.id).all()
                    )
                    for stale_we in stale_workout_exercises:
                        db.delete(stale_we)
                    db.flush()

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
                            exercise_index=parsed_exercise.exercise_index,
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
    }


async def _process_webhook_workout(workout_id: str) -> None:
    """Background task to fetch and upsert a Hevy workout."""
    logger = get_logger(__name__)
    if not settings.hevy_api_key:
        logger.warning("webhook_skipped_no_api_key")
        return

    try:
        async with HevyClient() as client:
            workout_data = await client.get_workout(workout_id)
    except HevyAPIError as exc:
        logger.error(
            "webhook_fetch_failed",
            workout_id=workout_id,
            error=str(exc),
            url=exc.url,
            method=exc.method,
            params=exc.params,
            status_code=exc.status_code,
            response_text=exc.response_text,
        )
        return

    from workout_mcp.database import SessionLocal

    db = SessionLocal()
    try:
        upsert_hevy_workout(db, workout_data)
        db.commit()
        logger.info("webhook_workout_upserted", workout_id=workout_id)
    except Exception as exc:
        db.rollback()
        logger.error("webhook_upsert_failed", workout_id=workout_id, error=str(exc))
    finally:
        db.close()


@app.post("/webhooks/hevy")
async def hevy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Receive Hevy webhook notifications."""
    data = await request.json()
    workout_id = data.get("workoutId")

    if not workout_id:
        raise HTTPException(status_code=400, detail="Missing workoutId")

    if not settings.hevy_api_key:
        raise HTTPException(status_code=503, detail="Hevy API not configured")

    background_tasks.add_task(_process_webhook_workout, workout_id)
    return {"status": "ok"}


@app.post("/sync/hevy", status_code=202)
async def sync_hevy(
    background_tasks: BackgroundTasks,
    mode: SyncMode = "incremental",
) -> dict[str, str]:
    """Trigger an on-demand Hevy sync.

    The sync runs in a background task.  Query parameter ``mode`` accepts:

    - ``"incremental"`` (default) — poll recent events via ``/v1/workouts/events``
    - ``"full"`` — fetch all workouts via ``/v1/workouts``
    """
    background_tasks.add_task(trigger_sync, SessionLocal, mode)
    return {"status": "sync_started", "mode": mode}
