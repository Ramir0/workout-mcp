from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from workout_mcp.hevy_mapper import map_hevy_workout_to_models
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_map_basic_workout() -> None:
    hevy_data: dict[str, Any] = {
        "id": "w1",
        "title": "Push Day",
        "description": "Chest and triceps",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "updated_at": "2024-01-01T12:00:00+00:00",
        "routine_name": "Push Day Routine",
        "exercises": [
            {
                "title": "Bench Press",
                "sets": [
                    {
                        "set_number": 0,
                        "weight_kg": 100.0,
                        "reps": 5,
                        "distance_meters": None,
                        "duration_seconds": None,
                        "rpe": 8.0,
                    }
                ],
            }
        ],
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert isinstance(routine, Routine)
    assert routine.name == "Push Day Routine"

    assert isinstance(workout, Workout)
    assert workout.title == "Push Day"
    assert workout.description == "Chest and triceps"
    assert workout.start == datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    assert workout.end == datetime(2024, 1, 1, 11, 0, tzinfo=UTC)
    assert workout.updated_at == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

    assert len(exercises) == 1
    assert isinstance(exercises[0], Exercise)
    assert exercises[0].name == "Bench Press"

    assert len(workout_exercises) == 1
    assert isinstance(workout_exercises[0], WorkoutExercise)
    assert workout_exercises[0].exercise_index == 0

    assert len(sets) == 1
    assert isinstance(sets[0], Set)
    assert sets[0].set_index == 0
    assert sets[0].weight == 100.0
    assert sets[0].reps == 5
    assert sets[0].rpe == 8.0
    assert sets[0].distance_km is None
    assert sets[0].duration_seconds is None


def test_map_hybrid_workout() -> None:
    hevy_data: dict[str, Any] = {
        "id": "w2",
        "title": "Cardio Day",
        "description": None,
        "start_time": "2024-01-02T08:00:00+00:00",
        "end_time": "2024-01-02T09:00:00+00:00",
        "updated_at": "2024-01-02T10:00:00+00:00",
        "routine_name": "Morning Run",
        "exercises": [
            {
                "title": "Running",
                "sets": [
                    {
                        "set_number": 0,
                        "weight_kg": None,
                        "reps": None,
                        "distance_meters": 5000,
                        "duration_seconds": 1800,
                        "rpe": None,
                    }
                ],
            }
        ],
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert routine.name == "Morning Run"
    assert workout.title == "Cardio Day"

    assert len(sets) == 1
    assert sets[0].distance_km == 5.0
    assert sets[0].duration_seconds == 1800
    assert sets[0].weight is None
    assert sets[0].reps is None


def test_map_workout_without_routine() -> None:
    hevy_data: dict[str, Any] = {
        "id": "w3",
        "title": "Quick Workout",
        "description": None,
        "start_time": "2024-01-03T07:00:00+00:00",
        "end_time": "2024-01-03T07:30:00+00:00",
        "updated_at": None,
        "routine_name": None,
        "exercises": [],
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert routine.name == "Quick Workout"
    assert workout.title == "Quick Workout"
    assert workout.updated_at is None
    assert len(exercises) == 0
