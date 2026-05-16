"""Unit tests for SQLAlchemy models (no database required)."""

from datetime import datetime

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_routine_instantiation() -> None:
    routine = Routine(name="Push Day")
    assert routine.name == "Push Day"
    assert routine.id is None


def test_workout_instantiation() -> None:
    start = datetime(2024, 1, 1, 10, 0, 0)
    end = datetime(2024, 1, 1, 11, 0, 0)
    workout = Workout(start=start, end=end)
    assert workout.start == start
    assert workout.end == end


def test_exercise_instantiation() -> None:
    exercise = Exercise(name="Bench Press")
    assert exercise.name == "Bench Press"


def test_workout_exercise_instantiation() -> None:
    we = WorkoutExercise(exercise_index=0)
    assert we.exercise_index == 0


def test_set_instantiation() -> None:
    set_ = Set(set_index=1, reps=10, weight=100.0, rpe=8.0)
    assert set_.reps == 10
    assert set_.weight == 100.0
    assert set_.rpe == 8.0


def test_set_optional_rpe() -> None:
    set_ = Set(set_index=1, reps=10, weight=100.0)
    assert set_.rpe is None


def test_relationship_backrefs() -> None:
    routine = Routine(name="Leg Day")
    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
    )
    workout.routine = routine
    assert workout in routine.workouts
    assert workout.routine is routine
