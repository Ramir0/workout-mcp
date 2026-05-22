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


def test_routine_repr() -> None:
    routine = Routine(id=1, name="Push Day")
    rep = repr(routine)
    assert "Routine" in rep
    assert "Push Day" in rep


def test_workout_repr() -> None:
    start = datetime(2024, 1, 1, 10, 0, 0)
    end = datetime(2024, 1, 1, 11, 0, 0)
    workout = Workout(id=1, start=start, end=end)
    rep = repr(workout)
    assert "Workout" in rep


def test_exercise_repr() -> None:
    exercise = Exercise(id=1, name="Bench Press")
    rep = repr(exercise)
    assert "Exercise" in rep
    assert "Bench Press" in rep


def test_workout_exercise_repr() -> None:
    we = WorkoutExercise(id=1, exercise_index=2)
    rep = repr(we)
    assert "WorkoutExercise" in rep


def test_set_repr() -> None:
    s = Set(id=1, set_index=3, reps=10, weight=100.0)
    rep = repr(s)
    assert "Set" in rep


def test_relationship_backrefs() -> None:
    routine = Routine(name="Leg Day")
    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
    )
    workout.routine = routine
    assert workout in routine.workouts
    assert workout.routine is routine
