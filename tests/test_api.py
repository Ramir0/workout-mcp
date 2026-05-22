"""Integration tests for the REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from workout_mcp.models import Exercise, Routine, Set, Workout

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_import_csv_success(client: TestClient, db_session: Session) -> None:
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 2
    assert data["created"]["workouts"] == 2
    assert data["created"]["exercises"] == 3
    assert data["created"]["workout_exercises"] == 3
    assert data["created"]["sets"] == 4
    assert data["discarded"]["sets"] == 0
    assert data["warnings"] == []

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
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 0
    assert data["created"]["workouts"] == 0
    assert data["created"]["exercises"] == 0
    assert data["created"]["workout_exercises"] == 0
    assert data["created"]["sets"] == 0
    assert data["discarded"]["sets"] == 4
    assert len(data["warnings"]) == 4
    assert all("already exists" in w["reason"] for w in data["warnings"])

    # Database must not have doubled
    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4


def test_import_csv_discards_existing_set(client: TestClient, db_session: Session) -> None:
    """Re-importing a workout with changed set data should discard the set, not update."""
    with open(FIXTURES_DIR / "sample_hevy.csv", "rb") as f:
        client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    # Modify weight in the CSV inline
    csv_path = FIXTURES_DIR / "sample_hevy.csv"
    csv_text = csv_path.read_text(encoding="utf-8")
    modified = csv_text.replace(
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8',
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",105,5,,0,8',
    )

    response = client.post(
        "/import/csv",
        files={"file": ("sample_hevy.csv", modified.encode("utf-8"))},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["workouts"] == 0
    assert data["discarded"]["sets"] == 4
    assert len(data["warnings"]) == 4

    # Original weight must be preserved (not updated) - set was discarded
    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    assert bench.workout_exercises[0].sets[0].weight == 100.0


def test_import_csv_empty_file(client: TestClient) -> None:
    with open(FIXTURES_DIR / "empty.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("empty.csv", f)})

    assert response.status_code == 400
    assert "no data rows" in response.json()["detail"]


def test_import_csv_non_csv_extension(client: TestClient) -> None:
    response = client.post(
        "/import/csv",
        files={"file": ("report.txt", b"not a csv")},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_import_csv_malformed_date(client: TestClient) -> None:
    with open(FIXTURES_DIR / "malformed_date.csv", "rb") as f:
        response = client.post("/import/csv", files={"file": ("malformed_date.csv", f)})

    assert response.status_code == 400
    assert "Unable to parse date" in response.json()["detail"]


def test_import_non_utf8_file(client: TestClient) -> None:
    """Non-UTF8 encoded file returns 400."""
    import io

    content = b"\x80\x81\x82\x83"
    files = {"file": ("test.csv", io.BytesIO(content), "text/csv")}
    response = client.post("/import/csv", files=files)
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_import_invalid_multipart(client: TestClient) -> None:
    """Missing file field returns 422."""
    response = client.post("/import/csv")
    assert response.status_code == 422


def test_request_middleware_adds_request_id(client: TestClient) -> None:
    """Request logging middleware adds X-Request-ID header."""
    import io

    response = client.post(
        "/import/csv",
        files={"file": ("test.csv", io.BytesIO(b"title:,Workout 1"), "text/csv")},
    )
    assert "X-Request-ID" in response.headers


def test_generic_exception_handler_returns_500() -> None:
    """Generic exception handler returns 500 for unhandled errors."""
    import io
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from workout_mcp.api import app

    client = TestClient(app, raise_server_exceptions=False)
    with patch("workout_mcp.api.parse_hevy_csv", side_effect=RuntimeError("Boom")):
        response = client.post(
            "/import/csv",
            files={"file": ("test.csv", io.BytesIO(b"some,valid,utf8,content"), "text/csv")},
        )
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


def test_import_csv_updates_exercise_index(client: TestClient) -> None:
    """Re-importing with changed exercise order updates exercise_index."""
    import io
    from pathlib import Path

    fixtures_dir = Path(__file__).parent / "fixtures"

    # Initial import
    with open(fixtures_dir / "sample_hevy.csv", "rb") as f:
        client.post("/import/csv", files={"file": ("sample_hevy.csv", f)})

    # Second import with swapped exercise order: Squat (index 0), Bench Press (index 1)
    header = '"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
    lines = (
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat","","",0,"normal",140,5,,0,9\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",1,"normal",100,5,,0,8.5\n'
    )
    response = client.post(
        "/import/csv",
        files={"file": ("swapped.csv", io.BytesIO((header + lines).encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created"]["workout_exercises"] == 0
    assert data["created"]["workouts"] == 0
