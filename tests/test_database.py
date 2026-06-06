"""Database integration tests verifying ORM round-trips."""

from datetime import datetime

from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_create_routine(db_session: Session) -> None:
    routine = Routine(name="Test Routine")
    db_session.add(routine)
    db_session.commit()

    result = db_session.query(Routine).filter_by(name="Test Routine").first()
    assert result is not None
    assert result.name == "Test Routine"


def test_create_workout_with_routine(db_session: Session) -> None:
    routine = Routine(name="Push Day")
    db_session.add(routine)
    db_session.commit()

    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
        routine=routine,
    )
    db_session.add(workout)
    db_session.commit()

    result = db_session.query(Workout).filter_by(routine_id=routine.id).first()
    assert result is not None
    assert result.routine.name == "Push Day"


def test_create_full_workout_hierarchy(db_session: Session) -> None:
    routine = Routine(name="Leg Day")
    db_session.add(routine)
    db_session.commit()

    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
        routine=routine,
    )
    db_session.add(workout)
    db_session.commit()

    exercise = Exercise(name="Squat")
    db_session.add(exercise)
    db_session.commit()

    workout_exercise = WorkoutExercise(
        workout=workout,
        exercise=exercise,
        exercise_index=0,
    )
    db_session.add(workout_exercise)
    db_session.commit()

    set_ = Set(
        workout_exercise=workout_exercise,
        set_index=1,
        reps=5,
        weight=100.0,
        rpe=8.0,
    )
    db_session.add(set_)
    db_session.commit()

    # Verify round-trip
    result_set = db_session.query(Set).filter_by(weight=100.0).first()
    assert result_set is not None
    assert result_set.workout_exercise.exercise.name == "Squat"
    assert result_set.workout_exercise.workout.routine.name == "Leg Day"


def test_transaction_isolation(db_session: Session) -> None:
    """Ensure data from this test is not visible in other tests."""
    routine = Routine(name="Isolation Test")
    db_session.add(routine)
    db_session.commit()

    count = db_session.query(Routine).filter_by(name="Isolation Test").count()
    assert count == 1


def test_same_exercise_can_appear_at_two_indices(db_session: Session) -> None:
    """The same exercise can appear in one workout at two different exercise_index values."""
    from datetime import datetime

    routine = Routine(name="Repeat Day")
    db_session.add(routine)
    db_session.flush()

    workout = Workout(
        start=datetime(2024, 1, 1, 10, 0, 0),
        end=datetime(2024, 1, 1, 11, 0, 0),
        routine=routine,
    )
    db_session.add(workout)
    db_session.flush()

    bench = Exercise(name="Bench Press")
    db_session.add(bench)
    db_session.flush()

    warmup = WorkoutExercise(workout=workout, exercise=bench, exercise_index=0)
    working_sets = WorkoutExercise(workout=workout, exercise=bench, exercise_index=9)
    db_session.add_all([warmup, working_sets])
    db_session.commit()

    rows = (
        db_session.query(WorkoutExercise)
        .filter_by(workout_id=workout.id, exercise_id=bench.id)
        .order_by(WorkoutExercise.exercise_index)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].exercise_index == 0
    assert rows[1].exercise_index == 9
