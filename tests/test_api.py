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
    assert data["created"]["workout_exercises"] == 4
    assert data["created"]["sets"] == 4
    assert data["discarded"]["sets"] == 0

    # Verify database state
    assert db_session.query(Routine).count() == 2
    assert db_session.query(Workout).count() == 2
    assert db_session.query(Exercise).count() == 3
    assert db_session.query(Set).count() == 4

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    # sample_hevy.csv has two consecutive Bench Press rows (set_index 0 and 1),
    # so each becomes its own WorkoutExercise with a single set under the new
    # occurrence-preserving parser.
    assert len(bench.workout_exercises) == 2
    for we in bench.workout_exercises:
        assert len(we.sets) == 1


def test_import_csv_idempotent(client: TestClient, db_session: Session) -> None:
    """Importing the same CSV twice must leave the final database state unchanged."""
    payload = _csv_payload(FIXTURES_DIR / "sample_hevy.csv")
    client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    response = client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 0
    assert data["created"]["workouts"] == 0
    assert data["created"]["exercises"] == 0
    # Re-imports wipe and recreate WorkoutExercise/Set rows for the matched
    # workout, so deltas reflect the replace-not-merge semantics.
    assert data["created"]["workout_exercises"] == 4
    assert data["created"]["sets"] == 4
    assert data["discarded"]["sets"] == 0

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
    # hybrid.csv has two consecutive Weighted Run rows (strength then cardio).
    # The new parser emits one ParsedExercise per occurrence, so we get two
    # WorkoutExercise rows, each holding the set for its exercise_index.
    assert len(exercise.workout_exercises) == 2
    we_by_index = sorted(exercise.workout_exercises, key=lambda we: we.exercise_index)
    assert len(we_by_index[0].sets) == 1
    assert we_by_index[0].sets[0].set_index == 0
    assert we_by_index[0].sets[0].weight == 20.0
    assert we_by_index[0].sets[0].duration_seconds is None
    assert len(we_by_index[1].sets) == 1
    assert we_by_index[1].sets[0].set_index == 1
    assert we_by_index[1].sets[0].weight is None
    assert we_by_index[1].sets[0].duration_seconds == 600


def test_import_csv_replaces_existing_set(client: TestClient, db_session: Session) -> None:
    """Re-importing wipes stale WorkoutExercise rows and recreates them with the new set data."""
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
    assert data["created"]["workout_exercises"] == 1
    assert data["created"]["sets"] == 1
    assert data["discarded"]["sets"] == 0

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    assert bench.workout_exercises[0].sets[0].weight == 999.0


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


def test_import_csv_replaces_workout_exercises_on_reimport(
    client: TestClient, db_session: Session
) -> None:
    """Re-importing a routine replaces its WorkoutExercise set, not merges with the old one."""
    from workout_mcp.models import WorkoutExercise

    payload = _csv_payload(FIXTURES_DIR / "sample_hevy.csv")
    client.post("/import/csv", content=payload, headers={"Content-Type": "text/csv"})

    push_workout = (
        db_session.query(Workout).join(Routine).filter(Routine.name == "Push Day").first()
    )
    assert push_workout is not None
    original_count = db_session.query(WorkoutExercise).filter_by(workout_id=push_workout.id).count()
    assert original_count == 3  # Bench@0, Bench@1, Squat

    # Reorder: Squat first, then one Bench Press for Push Day
    reordered = (
        '"title","start_time","end_time","description","exercise_title","superset_id",'
        '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat","","",0,"normal",140,5,,0,9\n'
        '"Push Day","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Bench Press","","",0,"normal",100,5,,0,8\n'
    )

    response = client.post(
        "/import/csv",
        content=reordered.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["workouts"] == 0
    assert data["created"]["exercises"] == 0
    assert data["created"]["workout_exercises"] == 2  # only the two new rows

    # The total WorkoutExercise count for the Push Day workout must still be 2,
    # because the old rows were replaced.
    final_count = db_session.query(WorkoutExercise).filter_by(workout_id=push_workout.id).count()
    assert final_count == 2

    # The Squat row is now at index 0, Bench Press at index 1.
    new_rows = (
        db_session.query(WorkoutExercise)
        .filter_by(workout_id=push_workout.id)
        .order_by(WorkoutExercise.exercise_index)
        .all()
    )
    assert new_rows[0].exercise.name == "Squat"
    assert new_rows[0].exercise_index == 0
    assert new_rows[1].exercise.name == "Bench Press"
    assert new_rows[1].exercise_index == 1


def test_import_csv_replaces_workout_exercises_growth_case(
    client: TestClient, db_session: Session
) -> None:
    """Re-importing a routine with MORE exercises still replaces the full set, never appends.

    Regression-locker for a future "partial-merge optimization" that only deletes
    WorkoutExercise rows absent from the new layout. That optimization would
    silently double-add exercises on growth (1 + 3 = 4 rows instead of 3).
    """
    from workout_mcp.models import WorkoutExercise

    initial = (
        '"title","start_time","end_time","description","exercise_title","superset_id",'
        '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
        '"Growth Test","Mar 1, 2024, 10:00 AM","Mar 1, 2024, 11:00 AM","","Bench Press","","",'
        '0,"normal",100,5,,0,8\n'
    )
    response = client.post(
        "/import/csv",
        content=initial.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    assert response.json()["created"]["workout_exercises"] == 1

    grown = (
        '"title","start_time","end_time","description","exercise_title","superset_id",'
        '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"\n'
        '"Growth Test","Mar 1, 2024, 10:00 AM","Mar 1, 2024, 11:00 AM","","Bench Press","","",'
        '0,"normal",100,5,,0,8\n'
        '"Growth Test","Mar 1, 2024, 10:00 AM","Mar 1, 2024, 11:00 AM","","Squat","","",'
        '0,"normal",140,5,,0,9\n'
        '"Growth Test","Mar 1, 2024, 10:00 AM","Mar 1, 2024, 11:00 AM","","Leg Press","","",'
        '0,"normal",200,5,,0,8\n'
    )
    response = client.post(
        "/import/csv",
        content=grown.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    assert response.json()["created"]["workout_exercises"] == 3

    workout = db_session.query(Workout).join(Routine).filter(Routine.name == "Growth Test").first()
    assert workout is not None
    rows = (
        db_session.query(WorkoutExercise)
        .filter_by(workout_id=workout.id)
        .order_by(WorkoutExercise.exercise_index)
        .all()
    )
    assert len(rows) == 3
    names = [r.exercise.name for r in rows]
    assert names == ["Bench Press", "Squat", "Leg Press"]
    assert len(set(names)) == 3


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


def test_import_csv_allows_duplicate_exercise_in_routine(
    client: TestClient, db_session: Session
) -> None:
    """A routine that contains the same exercise twice must import without error."""
    from workout_mcp.models import WorkoutExercise

    response = client.post(
        "/import/csv",
        content=_csv_payload(FIXTURES_DIR / "duplicate_exercise.csv"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 1
    assert data["created"]["workouts"] == 1
    assert data["created"]["exercises"] == 2  # Bench Press and Squat
    assert data["created"]["workout_exercises"] == 4  # warm-up, squat, bench x2
    assert data["created"]["sets"] == 4  # 1 + 1 + 1 + 1

    bench = db_session.query(Exercise).filter_by(name="Bench Press").first()
    assert bench is not None
    bench_rows = (
        db_session.query(WorkoutExercise)
        .filter_by(exercise_id=bench.id)
        .order_by(WorkoutExercise.exercise_index)
        .all()
    )
    assert len(bench_rows) == 3
    assert [r.exercise_index for r in bench_rows] == [0, 2, 3]
    assert sum(len(r.sets) for r in bench_rows) == 3


def test_sync_hevy_endpoint(client: TestClient) -> None:
    response = client.post("/sync/hevy")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "sync_started"
