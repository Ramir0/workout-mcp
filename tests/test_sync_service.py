from __future__ import annotations

from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise
from workout_mcp.sync_service import upsert_hevy_workout


def test_upsert_new_workout(db_session: Session) -> None:
    hevy_data = {
        "id": "w1",
        "title": "Push Day",
        "description": "Chest",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "updated_at": "2024-01-01T12:00:00+00:00",
        "routine_name": "Push Routine",
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

    upsert_hevy_workout(db_session, hevy_data)

    assert db_session.query(Routine).count() == 1
    assert db_session.query(Workout).count() == 1
    assert db_session.query(Exercise).count() == 1
    assert db_session.query(WorkoutExercise).count() == 1
    assert db_session.query(Set).count() == 1

    routine = db_session.query(Routine).first()
    assert routine is not None
    assert routine.name == "Push Routine"

    workout = db_session.query(Workout).first()
    assert workout is not None
    assert workout.title == "Push Day"
    assert workout.description == "Chest"


def test_upsert_existing_workout_replaces_data(db_session: Session) -> None:
    hevy_data_v1 = {
        "id": "w1",
        "title": "Push Day",
        "description": "Chest",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "updated_at": "2024-01-01T12:00:00+00:00",
        "routine_name": "Push Routine",
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

    upsert_hevy_workout(db_session, hevy_data_v1)
    original_workout = db_session.query(Workout).first()
    assert original_workout is not None
    original_workout_id = original_workout.id

    hevy_data_v2 = {
        "id": "w1",
        "title": "Push Day Updated",
        "description": "Chest and triceps",
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "updated_at": "2024-01-01T13:00:00+00:00",
        "routine_name": "Push Routine",
        "exercises": [
            {
                "title": "Bench Press",
                "sets": [
                    {
                        "set_number": 0,
                        "weight_kg": 105.0,
                        "reps": 5,
                        "distance_meters": None,
                        "duration_seconds": None,
                        "rpe": 8.5,
                    },
                    {
                        "set_number": 1,
                        "weight_kg": 105.0,
                        "reps": 5,
                        "distance_meters": None,
                        "duration_seconds": None,
                        "rpe": 8.5,
                    },
                ],
            }
        ],
    }

    upsert_hevy_workout(db_session, hevy_data_v2)

    workout = db_session.query(Workout).first()
    assert workout is not None
    assert workout.title == "Push Day Updated"
    assert workout.description == "Chest and triceps"
    assert workout.id != original_workout_id

    assert db_session.query(Set).count() == 2
    weights = {s.weight for s in db_session.query(Set).all()}
    assert weights == {105.0}


def test_upsert_reuses_existing_exercise(db_session: Session) -> None:
    hevy_data = {
        "id": "w1",
        "title": "Push Day",
        "description": None,
        "start_time": "2024-01-01T10:00:00+00:00",
        "end_time": "2024-01-01T11:00:00+00:00",
        "updated_at": None,
        "routine_name": "Push",
        "exercises": [
            {"title": "Bench Press", "sets": [{"set_number": 0, "weight_kg": 100, "reps": 5}]}
        ],
    }

    upsert_hevy_workout(db_session, hevy_data)
    exercise_count_after_first = db_session.query(Exercise).count()

    upsert_hevy_workout(db_session, hevy_data)
    exercise_count_after_second = db_session.query(Exercise).count()

    assert exercise_count_after_first == exercise_count_after_second
