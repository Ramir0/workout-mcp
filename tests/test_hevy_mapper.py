from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from workout_mcp.hevy_mapper import MapperError, map_hevy_workout_to_models, parse_datetime
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
    assert workout.routine is routine

    assert len(exercises) == 1
    assert isinstance(exercises[0], Exercise)
    assert exercises[0].name == "Bench Press"

    assert len(workout_exercises) == 1
    assert isinstance(workout_exercises[0], WorkoutExercise)
    assert workout_exercises[0].exercise_index == 0
    assert workout_exercises[0].workout is workout
    assert workout_exercises[0].exercise is exercises[0]

    assert len(sets) == 1
    assert isinstance(sets[0], Set)
    assert sets[0].set_index == 0
    assert sets[0].weight == 100.0
    assert sets[0].reps == 5
    assert sets[0].rpe == 8.0
    assert sets[0].distance_km is None
    assert sets[0].duration_seconds is None
    assert sets[0].workout_exercise is workout_exercises[0]


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
    assert workout.routine is routine

    assert len(workout_exercises) == 1
    assert workout_exercises[0].workout is workout
    assert workout_exercises[0].exercise is exercises[0]

    assert len(sets) == 1
    assert sets[0].distance_km == 5.0
    assert sets[0].duration_seconds == 1800
    assert sets[0].weight is None
    assert sets[0].reps is None
    assert sets[0].rpe is None
    assert sets[0].workout_exercise is workout_exercises[0]


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
    assert len(workout_exercises) == 0
    assert len(sets) == 0
    assert workout.routine is routine


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-01-01T10:00:00Z", datetime(2024, 1, 1, 10, 0, tzinfo=UTC)),
        ("2024-01-01T10:00:00+00:00", datetime(2024, 1, 1, 10, 0, tzinfo=UTC)),
        ("2024-01-01T10:00:00", datetime(2024, 1, 1, 10, 0, tzinfo=UTC)),
        (None, None),
    ],
)
def test_parse_datetime(raw: str | None, expected: datetime | None) -> None:
    assert parse_datetime(raw) == expected


def test_parse_datetime_invalid() -> None:
    with pytest.raises(MapperError, match="Invalid datetime string"):
        parse_datetime("not-a-datetime")


def test_missing_start_time() -> None:
    hevy_data: dict[str, Any] = {
        "title": "Test",
        "start_time": None,
        "end_time": "2024-01-01T11:00:00+00:00",
        "exercises": [],
    }
    with pytest.raises(MapperError, match="Missing required field: start_time"):
        map_hevy_workout_to_models(hevy_data)


def test_missing_end_time() -> None:
    hevy_data: dict[str, Any] = {
        "title": "Test",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": None,
        "exercises": [],
    }
    with pytest.raises(MapperError, match="Missing required field: end_time"):
        map_hevy_workout_to_models(hevy_data)


def test_null_exercises_list() -> None:
    hevy_data: dict[str, Any] = {
        "title": "Test",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "exercises": None,
    }
    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)
    assert len(exercises) == 0
    assert len(workout_exercises) == 0
    assert len(sets) == 0


def test_null_sets_list() -> None:
    hevy_data: dict[str, Any] = {
        "title": "Test",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "exercises": [
            {
                "title": "Squat",
                "sets": None,
            }
        ],
    }
    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)
    assert len(exercises) == 1
    assert len(workout_exercises) == 1
    assert len(sets) == 0


def test_null_set_number() -> None:
    hevy_data: dict[str, Any] = {
        "title": "Test",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "exercises": [
            {
                "title": "Squat",
                "sets": [
                    {
                        "set_number": None,
                        "weight_kg": 100.0,
                        "reps": 5,
                    }
                ],
            }
        ],
    }
    with pytest.raises(MapperError, match="Missing required field in set: set_number"):
        map_hevy_workout_to_models(hevy_data)


def test_multiple_exercises_and_sets() -> None:
    hevy_data: dict[str, Any] = {
        "id": "w4",
        "title": "Leg Day",
        "description": "Quad focused",
        "start_time": "2024-01-04T10:00:00+00:00",
        "end_time": "2024-01-04T11:00:00+00:00",
        "updated_at": None,
        "routine_name": "Leg Day Routine",
        "exercises": [
            {
                "title": "Squat",
                "sets": [
                    {"set_number": 0, "weight_kg": 100.0, "reps": 5, "rpe": 8.0},
                    {"set_number": 1, "weight_kg": 105.0, "reps": 5, "rpe": 9.0},
                ],
            },
            {
                "title": "Leg Press",
                "sets": [
                    {"set_number": 0, "weight_kg": 200.0, "reps": 10, "rpe": 7.0},
                    {"set_number": 1, "weight_kg": 210.0, "reps": 10, "rpe": 8.0},
                    {"set_number": 2, "weight_kg": 220.0, "reps": 8, "rpe": 9.0},
                ],
            },
        ],
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert len(exercises) == 2
    assert exercises[0].name == "Squat"
    assert exercises[1].name == "Leg Press"

    assert len(workout_exercises) == 2
    assert workout_exercises[0].exercise_index == 0
    assert workout_exercises[1].exercise_index == 1
    assert workout_exercises[0].workout is workout
    assert workout_exercises[0].exercise is exercises[0]
    assert workout_exercises[1].workout is workout
    assert workout_exercises[1].exercise is exercises[1]

    assert len(sets) == 5

    # Squat sets
    assert sets[0].set_index == 0
    assert sets[0].weight == 100.0
    assert sets[0].reps == 5
    assert sets[0].rpe == 8.0
    assert sets[0].workout_exercise is workout_exercises[0]

    assert sets[1].set_index == 1
    assert sets[1].weight == 105.0
    assert sets[1].reps == 5
    assert sets[1].rpe == 9.0
    assert sets[1].workout_exercise is workout_exercises[0]

    # Leg Press sets
    assert sets[2].set_index == 0
    assert sets[2].weight == 200.0
    assert sets[2].reps == 10
    assert sets[2].rpe == 7.0
    assert sets[2].workout_exercise is workout_exercises[1]

    assert sets[3].set_index == 1
    assert sets[3].weight == 210.0
    assert sets[3].reps == 10
    assert sets[3].rpe == 8.0
    assert sets[3].workout_exercise is workout_exercises[1]

    assert sets[4].set_index == 2
    assert sets[4].weight == 220.0
    assert sets[4].reps == 8
    assert sets[4].rpe == 9.0
    assert sets[4].workout_exercise is workout_exercises[1]
