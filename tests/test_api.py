"""Integration tests for the REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _csv_payload(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def test_import_csv_success(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/import/csv",
        content=_csv_payload(FIXTURES_DIR / "sample_hevy.csv"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 2
    assert data["created"]["workouts"] == 2
    assert data["created"]["exercises"] == 3
    assert data["created"]["workout_exercises"] == 3
    assert data["created"]["sets"] == 4
    assert data["discarded"]["sets"] == 0

    # Verify database state
    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    assert len(bench.workout_exercises) == 1
    assert len(bench.workout_exercises[0].sets) == 2


def test_import_csv_idempotent(client: TestClient, db_session: Session) -> None:
    """Importing the same CSV twice must be fully idempotent - no duplicates."""
    payload = _csv_payload(FIXTURES_DIR / "sample_hevy.csv")
    client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    response = client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 0
    assert data["created"]["workouts"] == 0
    assert data["created"]["exercises"] == 0
    assert data["created"]["workout_exercises"] == 0
    assert data["created"]["sets"] == 0

    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4


def test_import_csv_hybrid_workout(client: TestClient, db_session: Session) -> None:
    """A workout with both duration_seconds and weight_kg creates sets with matching fields."""
    response = client.post(
        "/import/csv",
        content=_csv_payload(FIXTURES_DIR / "hybrid.csv"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["sets"] == 2

    routine = db_session.query(Routine).filter_by(name="Hybrid Day").first()
    assert routine is not None
    assert len(routine.workouts) == 1
    exercise = db_session.query(Exercise).filter_by(name="Weighted Run").first()
    assert exercise is not None
    assert len(exercise.workout_exercises) == 1
    sets = sorted(exercise.workout_exercises[0].sets, key=lambda s: s.set_index)
    assert sets[0].weight == 20.0
    assert sets[0].duration_seconds is None
    assert sets[1].weight is None
    assert sets[1].duration_seconds == 600


def test_import_csv_discards_existing_set(client: TestClient, db_session: Session) -> None:
    """When a workout_exercise already has a set with the same set_index, it is discarded."""
    payload = _csv_payload(FIXTURES_DIR / "sample_hevy.csv")
    client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    # Modify one set's weight so it would differ, but keep the same set_index
    modified = (
        '"title","start_time","end_time","description","exercise_title","superset_id",'
        '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",'
        '"0","normal",999,5,,0,8\n'
    )
    response = client.post(
        "/import/csv", content=modified.encode("utf-8"), headers={"Content-Type": "text/csv"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["sets"] == 0
    assert data["discarded"]["sets"] == 1

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    assert bench.workout_exercises[0].sets[0].weight == 100.0


def test_import_csv_empty_file(client: TestClient) -> None:
    response = client.post(
        "/import/csv",
        content=_csv_payload(FIXTURES_DIR / "empty.csv"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 400
    assert "no data rows" in response.json()["detail"]


def test_import_csv_non_csv_content_type(client: TestClient) -> None:
    response = client.post(
        "/import/csv",
        content=b"not a csv",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert "Content-Type must be text/csv" in response.json()["detail"]


def test_import_csv_malformed_date(client: TestClient) -> None:
    response = client.post(
        "/import/csv",
        content=_csv_payload(FIXTURES_DIR / "malformed_date.csv"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 400
    assert "Unable to parse date" in response.json()["detail"]


def test_import_non_utf8_file(client: TestClient) -> None:
    """Non-UTF8 encoded file returns 400."""
    response = client.post(
        "/import/csv",
        content=b"\x80\x81\x82\x83",
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_import_csv_updates_exercise_index(client: TestClient, db_session: Session) -> None:
    """Re-importing with reordered exercises updates exercise_index on existing workout_exercises."""
    from workout_mcp.models import WorkoutExercise

    payload = _csv_payload(FIXTURES_DIR / "sample_hevy.csv")
    client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    bench_we = db_session.query(WorkoutExercise).filter_by(exercise_id=bench.id).first()
    assert bench_we is not None
    original_index = bench_we.exercise_index

    # Reorder: Squat rows first, then Bench Press rows for Push Day
    reordered = (
        '"title","start_time","end_time","description","exercise_title","superset_id",'
        '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat","","",0,"normal",140,5,,0,9\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",1,"normal",100,5,,0,8.5\n'
        '"Pull Day","Jan 2, 2024, 10:00 AM","Jan 2, 2024, 11:00 AM","","Deadlift","","",0,"normal",180,5,,0,9\n'
    )

    response = client.post(
        "/import/csv",
        content=reordered.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["workout_exercises"] == 0
    assert data["created"]["sets"] == 0
    assert data["discarded"]["sets"] == 4

    # Exercise index should have changed
    db_session.refresh(bench_we)
    assert bench_we.exercise_index != original_index


def test_import_missing_body(client: TestClient) -> None:
    """Missing body or wrong Content-Type returns 400."""
    response = client.post("/import/csv")
    assert response.status_code == 400
    assert "Content-Type must be text/csv" in response.json()["detail"]


def test_request_middleware_adds_request_id(client: TestClient) -> None:
    """Request logging middleware adds X-Request-ID header."""
    response = client.post(
        "/import/csv",
        content=b"title:,Workout 1",
        headers={"Content-Type": "text/csv"},
    )
    assert "X-Request-ID" in response.headers


def test_generic_exception_handler_returns_500() -> None:
    """Generic exception handler returns 500 for unhandled errors."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from workout_mcp.api import app

    client = TestClient(app, raise_server_exceptions=False)
    with patch("workout_mcp.api.parse_hevy_csv", side_effect=RuntimeError("Boom")):
        response = client.post(
            "/import/csv",
            content=b"some,valid,utf8,content",
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


def test_import_csv_with_bom(client: TestClient, db_session: Session) -> None:
    """CSV with UTF-8 BOM prefix should import successfully."""
    csv_bytes = (
        '\ufeff"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"Legs","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat",'
        '"","",0,"normal",100,5,,0,\n'
    ).encode()
    response = client.post(
        "/import/csv",
        content=csv_bytes,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 1
    assert data["created"]["sets"] == 1
