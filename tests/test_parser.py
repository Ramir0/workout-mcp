"""Unit tests for the Hevy CSV parser."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pytest

from workout_mcp.parser import (
    EmptyCSVError,
    InvalidValueError,
    MalformedDateError,
    MissingColumnError,
    parse_hevy_csv,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_valid_csv() -> None:
    with open(FIXTURES_DIR / "sample_hevy.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 2

    # Push Day
    push = next(r for r in routines if r.name == "Push Day")
    assert len(push.workouts) == 1
    workout = push.workouts[0]
    assert workout.start == datetime(2024, 1, 1, 10, 0)
    assert workout.end == datetime(2024, 1, 1, 11, 0)
    assert len(workout.exercises) == 2

    bench = workout.exercises[0]
    assert bench.name == "Bench Press"
    assert bench.exercise_index == 0
    assert len(bench.sets) == 2
    assert bench.sets[0].set_index == 0
    assert bench.sets[0].weight == 100.0
    assert bench.sets[0].reps == 5
    assert bench.sets[0].rpe == 8.0

    squat = workout.exercises[1]
    assert squat.name == "Squat"
    assert squat.exercise_index == 1
    assert len(squat.sets) == 1
    assert squat.sets[0].weight == 140.0

    # Pull Day
    pull = next(r for r in routines if r.name == "Pull Day")
    assert len(pull.workouts) == 1
    deadlift = pull.workouts[0].exercises[0]
    assert deadlift.name == "Deadlift"
    assert deadlift.sets[0].weight == 180.0


def test_parse_from_string_io() -> None:
    csv_text = (
        '"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"Legs","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat",'
        '"","",0,"normal",100,5,,0,\n'
    )
    routines = parse_hevy_csv(io.StringIO(csv_text))
    assert len(routines) == 1
    assert routines[0].workouts[0].exercises[0].sets[0].rpe is None


def test_empty_csv() -> None:
    with (
        open(FIXTURES_DIR / "empty.csv", encoding="utf-8") as f,
        pytest.raises(EmptyCSVError, match="no data rows"),
    ):
        parse_hevy_csv(f)


def test_missing_required_columns() -> None:
    with (
        open(FIXTURES_DIR / "missing_columns.csv", encoding="utf-8") as f,
        pytest.raises(MissingColumnError, match="title"),
    ):
        parse_hevy_csv(f)


def test_malformed_date() -> None:
    with (
        open(FIXTURES_DIR / "malformed_date.csv", encoding="utf-8") as f,
        pytest.raises(MalformedDateError, match="not-a-date"),
    ):
        parse_hevy_csv(f)


def test_negative_weight() -> None:
    with (
        open(FIXTURES_DIR / "invalid_weight.csv", encoding="utf-8") as f,
        pytest.raises(InvalidValueError, match="non-negative"),
    ):
        parse_hevy_csv(f)


def test_weight_without_reps() -> None:
    """Weight present without reps is valid (at least one metric)."""
    with open(FIXTURES_DIR / "weight_without_reps.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 1
    set_ = routines[0].workouts[0].exercises[0].sets[0]
    assert set_.weight == 100.0
    assert set_.reps is None
    assert set_.distance_km is None
    assert set_.duration_seconds is None


def test_cardio_row() -> None:
    with open(FIXTURES_DIR / "cardio.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 1
    set_ = routines[0].workouts[0].exercises[0].sets[0]
    assert set_.weight is None
    assert set_.reps is None
    assert set_.distance_km == 0.5
    assert set_.duration_seconds == 600
    assert set_.rpe is None


def test_treadmill_weight_empty_reps_zero() -> None:
    """Weight empty with reps=0 and distance/duration present."""
    with open(FIXTURES_DIR / "treadmill.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 1
    set_ = routines[0].workouts[0].exercises[0].sets[0]
    assert set_.weight is None
    assert set_.reps == 0
    assert set_.distance_km == 0.7
    assert set_.duration_seconds == 600


def test_exercise_order_preserved() -> None:
    csv_text = (
        '"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","B",'
        '"","",0,"normal",10,1,,0,\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","C",'
        '"","",0,"normal",20,2,,0,\n'
        '"A","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","B",'
        '"","",1,"normal",15,1,,0,\n'
    )
    routines = parse_hevy_csv(io.StringIO(csv_text))
    exercises = routines[0].workouts[0].exercises
    assert exercises[0].name == "B"
    assert exercises[0].exercise_index == 0
    assert exercises[1].name == "C"
    assert exercises[1].exercise_index == 1
    assert len(exercises[0].sets) == 2


def test_hybrid_exercise() -> None:
    """Same exercise with both strength and cardio sets."""
    with open(FIXTURES_DIR / "hybrid.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    assert len(routines) == 1
    sets = routines[0].workouts[0].exercises[0].sets
    assert len(sets) == 2
    assert sets[0].weight == 20.0
    assert sets[0].reps == 5
    assert sets[0].distance_km is None
    assert sets[0].duration_seconds is None
    assert sets[1].weight is None
    assert sets[1].reps is None
    assert sets[1].distance_km == 2.0
    assert sets[1].duration_seconds == 600


def test_all_empty_metrics_error() -> None:
    """Row with no metrics at all should raise InvalidValueError."""
    with (
        open(FIXTURES_DIR / "all_empty_metrics.csv", encoding="utf-8") as f,
        pytest.raises(InvalidValueError, match="At least one"),
    ):
        parse_hevy_csv(f)


def test_distance_and_duration_parsed() -> None:
    """Parser should capture distance_km and duration_seconds."""
    with open(FIXTURES_DIR / "cardio_only.csv", encoding="utf-8") as f:
        routines = parse_hevy_csv(f)

    set_ = routines[0].workouts[0].exercises[0].sets[0]
    assert set_.distance_km == 5.0
    assert set_.duration_seconds == 1800
