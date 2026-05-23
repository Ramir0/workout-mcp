"""Map Hevy API workout JSON to SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime."""
    if value is None:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def map_hevy_workout_to_models(
    hevy_data: dict[str, Any],
) -> tuple[Routine, Workout, list[Exercise], list[WorkoutExercise], list[Set]]:
    """Transform a Hevy API workout dict into our ORM model instances.

    Returns:
        (routine, workout, exercises, workout_exercises, sets)
    """
    title = hevy_data.get("title") or "Untitled Workout"
    description = hevy_data.get("description")
    start_time = parse_datetime(hevy_data.get("start_time"))
    end_time = parse_datetime(hevy_data.get("end_time"))
    updated_at = parse_datetime(hevy_data.get("updated_at"))
    routine_name = hevy_data.get("routine_name") or title

    routine = Routine(name=routine_name)
    workout = Workout(
        start=start_time,
        end=end_time,
        title=title,
        description=description,
        updated_at=updated_at,
        routine=routine,
    )

    exercises: list[Exercise] = []
    workout_exercises: list[WorkoutExercise] = []
    sets: list[Set] = []

    for exercise_index, exercise_data in enumerate(hevy_data.get("exercises", [])):
        exercise_name = exercise_data.get("title") or "Unknown Exercise"
        exercise = Exercise(name=exercise_name)
        exercises.append(exercise)

        workout_exercise = WorkoutExercise(
            workout=workout,
            exercise=exercise,
            exercise_index=exercise_index,
        )
        workout_exercises.append(workout_exercise)

        for set_data in exercise_data.get("sets", []):
            weight = set_data.get("weight_kg")
            reps = set_data.get("reps")
            rpe = set_data.get("rpe")
            distance_meters = set_data.get("distance_meters")
            duration_seconds = set_data.get("duration_seconds")

            distance_km = distance_meters / 1000.0 if distance_meters is not None else None

            set_ = Set(
                workout_exercise=workout_exercise,
                set_index=set_data.get("set_number", 0),
                reps=reps,
                weight=weight,
                rpe=rpe,
                distance_km=distance_km,
                duration_seconds=duration_seconds,
            )
            sets.append(set_)

    return routine, workout, exercises, workout_exercises, sets
