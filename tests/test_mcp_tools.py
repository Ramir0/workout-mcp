"""Integration tests for MCP tools."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def _seed_workouts(db: Session) -> None:
    """Seed test data: Push Day (Jan 1), Pull Day (Jan 2), Push Day (Jan 3)."""
    push_routine = Routine(name="Push Day")
    pull_routine = Routine(name="Pull Day")
    db.add_all([push_routine, pull_routine])
    db.flush()

    push_workout_1 = Workout(
        start=datetime(2024, 1, 1, 10, 0),
        end=datetime(2024, 1, 1, 11, 0),
        routine=push_routine,
    )
    pull_workout = Workout(
        start=datetime(2024, 1, 2, 10, 0),
        end=datetime(2024, 1, 2, 11, 0),
        routine=pull_routine,
    )
    push_workout_2 = Workout(
        start=datetime(2024, 1, 3, 10, 0),
        end=datetime(2024, 1, 3, 11, 0),
        routine=push_routine,
    )
    db.add_all([push_workout_1, pull_workout, push_workout_2])
    db.flush()

    bench = Exercise(name="Bench Press")
    squat = Exercise(name="Squat")
    deadlift = Exercise(name="Deadlift")
    db.add_all([bench, squat, deadlift])
    db.flush()

    we_bench_1 = WorkoutExercise(workout=push_workout_1, exercise=bench, exercise_index=0)
    we_squat = WorkoutExercise(workout=push_workout_1, exercise=squat, exercise_index=1)
    we_deadlift = WorkoutExercise(workout=pull_workout, exercise=deadlift, exercise_index=0)
    we_bench_2 = WorkoutExercise(workout=push_workout_2, exercise=bench, exercise_index=0)
    db.add_all([we_bench_1, we_squat, we_deadlift, we_bench_2])
    db.flush()

    sets = [
        Set(workout_exercise=we_bench_1, set_index=0, reps=5, weight=80.0, rpe=7.0),
        Set(workout_exercise=we_bench_1, set_index=1, reps=5, weight=100.0, rpe=8.5),
        Set(workout_exercise=we_squat, set_index=0, reps=5, weight=140.0, rpe=9.0),
        Set(workout_exercise=we_deadlift, set_index=0, reps=5, weight=180.0, rpe=9.0),
        Set(workout_exercise=we_bench_2, set_index=0, reps=3, weight=120.0, rpe=9.5),
    ]
    db.add_all(sets)
    db.commit()


def test_get_workout_by_date_range(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_date_range

    results = _get_workout_by_date_range(db_session, "2024-01-01", "2024-01-01")
    assert len(results) == 1
    assert results[0]["routine"] == "Push Day"
    assert len(results[0]["exercises"]) == 2  # type: ignore[arg-type]


def test_get_workout_by_date_range_full_month(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_date_range

    results = _get_workout_by_date_range(db_session, "2024-01-01", "2024-01-31")
    assert len(results) == 3


def test_get_workout_by_date_range_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_date_range

    results = _get_workout_by_date_range(db_session, "2025-01-01", "2025-01-31")
    assert results == []


def test_get_workout_by_routine(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_routine

    results = _get_workout_by_routine(db_session, "Push Day")
    assert len(results) == 2
    assert results[0]["routine"] == "Push Day"
    exercise_names = [e["name"] for e in results[0]["exercises"]]  # type: ignore[attr-defined]
    assert "Bench Press" in exercise_names
    assert "Squat" in exercise_names


def test_get_workout_by_routine_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_routine

    results = _get_workout_by_routine(db_session, "Nonexistent")
    assert results == []


def test_get_workout_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_exercise

    results = _get_workout_by_exercise(db_session, "Bench Press")
    assert len(results) == 2
    assert results[0]["routine"] == "Push Day"
    # Should include ALL exercises for the workout, not just Bench Press
    assert len(results[0]["exercises"]) == 2  # type: ignore[arg-type]


def test_get_workout_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_by_exercise

    results = _get_workout_by_exercise(db_session, "Curls")
    assert results == []


def test_get_workout_count(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_count

    assert _get_workout_count(db_session) == 3
    assert _get_workout_count(db_session, routine_name="Push Day") == 2
    assert _get_workout_count(db_session, start_date="2024-01-02", end_date="2024-01-02") == 1
    assert _get_workout_count(db_session, routine_name="Nonexistent") == 0


def test_get_workout_count_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_workout_count

    assert _get_workout_count(db_session, start_date="2025-01-01", end_date="2025-01-31") == 0


def test_get_last_workout(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_last_workout

    result = _get_last_workout(db_session)
    assert result["routine"] == "Push Day"
    assert result["start"] == "2024-01-03T10:00:00"


def test_get_last_workout_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_last_workout

    result = _get_last_workout(db_session, exercise_name="Bench Press")
    assert result["routine"] == "Push Day"
    assert result["start"] == "2024-01-03T10:00:00"
    exercise_names = [e["name"] for e in result["exercises"]]  # type: ignore[attr-defined]
    assert "Bench Press" in exercise_names


def test_get_last_workout_by_exercise_not_most_recent(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_last_workout

    result = _get_last_workout(db_session, exercise_name="Squat")
    # Squat is only in Jan 1 workout, not Jan 3
    assert result["routine"] == "Push Day"
    assert result["start"] == "2024-01-01T10:00:00"


def test_get_last_workout_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_last_workout

    result = _get_last_workout(db_session, exercise_name="Nonexistent")
    assert result == {}


def test_get_max_pr_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_max_pr_by_exercise

    result = _get_max_pr_by_exercise(db_session, "Bench Press")
    assert result["weight"] == 120.0
    assert result["reps"] == 3
    assert "2024-01-03" in result["date"]  # type: ignore[operator]


def test_get_max_pr_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_max_pr_by_exercise

    result = _get_max_pr_by_exercise(db_session, "Nonexistent")
    assert result == {}


def test_get_min_pr_by_exercise(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_min_pr_by_exercise

    result = _get_min_pr_by_exercise(db_session, "Bench Press")
    assert result["weight"] == 100.0
    assert result["reps"] == 5
    assert "2024-01-01" in result["date"]  # type: ignore[operator]


def test_get_min_pr_by_exercise_empty(db_session: Session) -> None:
    _seed_workouts(db_session)
    from workout_mcp.mcp_server import _get_min_pr_by_exercise

    result = _get_min_pr_by_exercise(db_session, "Nonexistent")
    assert result == {}


@pytest.mark.xfail(reason="Error handling not implemented yet — will pass after Issue #17")
def test_get_workout_by_date_range_malformed_dates(db_session: Session) -> None:
    """Malformed date strings return error dict."""
    from workout_mcp.mcp_server import _get_workout_by_date_range

    result = _get_workout_by_date_range(db_session, "not-a-date", "2025-01-01")
    assert isinstance(result, dict)
    assert "error" in result


@pytest.mark.xfail(reason="Error handling not implemented yet — will pass after Issue #17")
def test_get_workout_count_malformed_date(db_session: Session) -> None:
    """Malformed date in count query returns error dict."""
    from workout_mcp.mcp_server import _get_workout_count

    result = _get_workout_count(db_session, start_date="bad-date")
    assert isinstance(result, dict)
    assert "error" in result
