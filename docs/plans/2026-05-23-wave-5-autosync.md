# Autosync from Hevy API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic sync from Hevy API via webhooks (real-time) and scheduled fallback polling, reusing existing database models and upsert logic.

**Architecture:** A thin Hevy API client (`hevy_client.py`) wraps `httpx.AsyncClient` with custom exceptions. A data mapper (`hevy_mapper.py`) transforms Hevy JSON into our ORM models. A sync service (`sync_service.py`) handles DB upserts using existing unique constraints (delete-and-replace for updated workouts). A webhook endpoint (`POST /webhooks/hevy`) acknowledges immediately and offloads processing to `BackgroundTasks`. A scheduled fallback job (`sync.py`) polls `/v1/workouts/events` via `APScheduler` and updates a `sync_state` watermark.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, httpx, APScheduler 3.x, structlog

---

## File Map

| File | Responsibility |
|------|--------------|
| `pyproject.toml` | Add `apscheduler` dependency |
| `workout_mcp/config.py` | Add Hevy API settings (api key, base url, webhook secret, sync interval) |
| `alembic/versions/` | Migration: add `sync_state` table and `title`/`description`/`updated_at` to `workout` |
| `workout_mcp/models.py` | Add `SyncState` model, add fields to `Workout` |
| `workout_mcp/hevy_client.py` | Async HTTP client for Hevy API with custom exceptions |
| `workout_mcp/hevy_mapper.py` | Transform Hevy API workout JSON into Routine/Workout/Exercise/WorkoutExercise/Set |
| `workout_mcp/sync_service.py` | Upsert Hevy workout data into DB using existing unique constraints |
| `workout_mcp/api.py` | Add `POST /webhooks/hevy` endpoint with BackgroundTasks; add app lifespan for scheduler |
| `workout_mcp/sync.py` | APScheduler fallback sync job (`sync_hevy_workouts`) |
| `tests/test_hevy_client.py` | Unit tests for HevyClient (mocked httpx) |
| `tests/test_hevy_mapper.py` | Unit tests for data mapping |
| `tests/test_sync_service.py` | Unit tests for DB upsert logic |
| `tests/test_webhook.py` | Integration tests for webhook endpoint |
| `tests/test_sync.py` | Integration tests for fallback sync job |

---

### Task 1: Add APScheduler dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `apscheduler` to dependencies**

In `pyproject.toml`, add `"apscheduler>=3.10,<4.0",` to the `[project] dependencies` list.

- [ ] **Step 2: Run `uv sync` to install**

```bash
uv sync
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add apscheduler for fallback sync"
```

---

### Task 2: Add Hevy API configuration fields

**Files:**
- Modify: `workout_mcp/config.py`
- Create or modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create or modify `tests/test_config.py`:

```python
from __future__ import annotations

import os

from workout_mcp.config import Settings


def test_hevy_config_fields() -> None:
    os.environ["HEVY_API_KEY"] = "test-api-key-123"
    os.environ["HEVY_BASE_URL"] = "https://api.hevyapp.com"
    os.environ["HEVY_WEBHOOK_SECRET"] = "super-secret"
    os.environ["HEVY_SYNC_INTERVAL_MINUTES"] = "60"

    settings = Settings()
    assert settings.hevy_api_key == "test-api-key-123"
    assert str(settings.hevy_base_url) == "https://api.hevyapp.com/"
    assert settings.hevy_webhook_secret == "super-secret"
    assert settings.hevy_sync_interval_minutes == 60

    del os.environ["HEVY_API_KEY"]
    del os.environ["HEVY_BASE_URL"]
    del os.environ["HEVY_WEBHOOK_SECRET"]
    del os.environ["HEVY_SYNC_INTERVAL_MINUTES"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py::test_hevy_config_fields -v
```

Expected: `AttributeError: 'Settings' object has no attribute 'hevy_api_key'`

- [ ] **Step 3: Add fields to Settings**

Modify `workout_mcp/config.py`, add to the `Settings` class after existing fields:

```python
    # Hevy API configuration
    hevy_api_key: str | None = None
    hevy_base_url: HttpUrl = "https://api.hevyapp.com"
    hevy_webhook_secret: str | None = None
    hevy_sync_interval_minutes: int = 360
```

Also add `from pydantic import HttpUrl` to imports if not present.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py::test_hevy_config_fields -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/config.py tests/test_config.py
git commit -m "feat: add Hevy API configuration fields"
```

---

### Task 3: Database migration — sync_state table and workout fields

**Files:**
- Modify: `workout_mcp/models.py`
- Create: `alembic/versions/<rev>_add_sync_state_and_workout_fields.py`

- [ ] **Step 1: Update models**

Add `SyncState` model and new fields to `Workout` in `workout_mcp/models.py`:

```python
class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"SyncState(id={self.id!r}, last_sync_at={self.last_sync_at!r})"
```

Add to `Workout` class:

```python
    title: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)
```

- [ ] **Step 2: Generate migration**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic revision --autogenerate -m "add sync_state and workout fields"
```

- [ ] **Step 3: Review migration file**

Check `alembic/versions/<rev>_add_sync_state_and_workout_fields.py` to ensure it:
- Creates `sync_state` table with `id`, `last_sync_at`, `updated_at`
- Adds `title`, `description`, `updated_at` columns to `workout`

- [ ] **Step 4: Run migration locally**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp uv run alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/models.py alembic/versions/
git commit -m "feat: add sync_state table and workout fields for API sync"
```

---

### Task 4: Create Hevy API client

**Files:**
- Create: `workout_mcp/hevy_client.py`
- Test: `tests/test_hevy_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hevy_client.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from workout_mcp.hevy_client import (
    HevyAPIError,
    HevyAuthError,
    HevyClient,
    HevyRateLimitError,
)


@pytest.fixture
def client() -> HevyClient:
    return HevyClient(api_key="test-key")


@pytest.mark.anyio
async def test_get_workout_success(client: HevyClient) -> None:
    mock_response = httpx.Response(200, json={"id": "w1", "title": "Push Day"})
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_workout("w1")
    assert result["id"] == "w1"
    assert result["title"] == "Push Day"


@pytest.mark.anyio
async def test_get_workout_not_found(client: HevyClient) -> None:
    mock_response = httpx.Response(404, json={"error": "not found"})
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(HevyAPIError, match="404"):
            await client.get_workout("w1")


@pytest.mark.anyio
async def test_get_workout_rate_limit(client: HevyClient) -> None:
    mock_response = httpx.Response(429)
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(HevyRateLimitError):
            await client.get_workout("w1")


@pytest.mark.anyio
async def test_get_workout_auth_error(client: HevyClient) -> None:
    mock_response = httpx.Response(401)
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(HevyAuthError):
            await client.get_workout("w1")


@pytest.mark.anyio
async def test_get_workout_events(client: HevyClient) -> None:
    since = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_response = httpx.Response(
        200,
        json={"events": [{"type": "updated", "workout": {"id": "w1", "title": "Leg Day"}}]},
    )
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_workout_events(since)
    assert len(result["events"]) == 1


@pytest.mark.anyio
async def test_get_workouts(client: HevyClient) -> None:
    mock_response = httpx.Response(200, json={"workouts": [{"id": "w1", "title": "Push Day"}]})
    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_workouts()
    assert len(result["workouts"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_hevy_client.py -v
```

Expected: ImportError for `workout_mcp.hevy_client`

- [ ] **Step 3: Implement HevyClient**

Create `workout_mcp/hevy_client.py`:

```python
"""Async HTTP client for the Hevy API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from workout_mcp.config import settings
from workout_mcp.logging import get_logger

logger = get_logger(__name__)


class HevyAPIError(Exception):
    """Base exception for Hevy API errors."""

    pass


class HevyRateLimitError(HevyAPIError):
    """Raised when Hevy returns HTTP 429."""

    pass


class HevyAuthError(HevyAPIError):
    """Raised when Hevy returns HTTP 401 or 403."""

    pass


class HevyClient:
    """Thin async wrapper around the Hevy REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.hevy_api_key or ""
        self.base_url = str(base_url or settings.hevy_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"api-key": self.api_key},
            timeout=30.0,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = await self._client.request(method, url, **kwargs)

        if response.status_code == 429:
            raise HevyRateLimitError("Hevy API rate limit exceeded")
        if response.status_code in (401, 403):
            raise HevyAuthError(f"Hevy API auth error: {response.status_code}")
        if response.status_code >= 400:
            raise HevyAPIError(
                f"Hevy API error {response.status_code}: {response.text}"
            )

        return response.json()

    async def get_workout(self, workout_id: str) -> dict[str, Any]:
        """Fetch a single workout by ID."""
        return await self._request("GET", f"/v1/workouts/{workout_id}")

    async def get_workout_events(
        self, since: datetime, page: int = 1, page_size: int = 10
    ) -> dict[str, Any]:
        """Fetch paginated workout events (updates and deletions) since a timestamp."""
        since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "since": since_iso,
            "page": page,
            "pageSize": page_size,
        }
        return await self._request("GET", "/v1/workouts/events", params=params)

    async def get_workouts(self, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """Fetch paginated list of all workouts."""
        params = {"page": page, "pageSize": page_size}
        return await self._request("GET", "/v1/workouts", params=params)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HevyClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_hevy_client.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/hevy_client.py tests/test_hevy_client.py
git commit -m "feat: add Hevy API client with error handling"
```

---

### Task 5: Create Hevy data mapper

**Files:**
- Create: `workout_mcp/hevy_mapper.py`
- Test: `tests/test_hevy_mapper.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hevy_mapper.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from workout_mcp.hevy_mapper import map_hevy_workout_to_models
from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def test_map_basic_workout() -> None:
    hevy_data = {
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
                ]
            }
        ]
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert isinstance(routine, Routine)
    assert routine.name == "Push Day Routine"

    assert isinstance(workout, Workout)
    assert workout.title == "Push Day"
    assert workout.description == "Chest and triceps"
    assert workout.start == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert workout.end == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
    assert workout.updated_at == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert len(exercises) == 1
    assert isinstance(exercises[0], Exercise)
    assert exercises[0].name == "Bench Press"

    assert len(workout_exercises) == 1
    assert isinstance(workout_exercises[0], WorkoutExercise)
    assert workout_exercises[0].exercise_index == 0

    assert len(sets) == 1
    assert isinstance(sets[0], Set)
    assert sets[0].set_index == 0
    assert sets[0].weight == 100.0
    assert sets[0].reps == 5
    assert sets[0].rpe == 8.0
    assert sets[0].distance_km is None
    assert sets[0].duration_seconds is None


def test_map_hybrid_workout() -> None:
    hevy_data = {
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
                ]
            }
        ]
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert routine.name == "Morning Run"
    assert workout.title == "Cardio Day"

    assert len(sets) == 1
    assert sets[0].distance_km == 5.0
    assert sets[0].duration_seconds == 1800
    assert sets[0].weight is None
    assert sets[0].reps is None


def test_map_workout_without_routine() -> None:
    hevy_data = {
        "id": "w3",
        "title": "Quick Workout",
        "description": None,
        "start_time": "2024-01-03T07:00:00+00:00",
        "end_time": "2024-01-03T07:30:00+00:00",
        "updated_at": None,
        "routine_name": None,
        "exercises": []
    }

    routine, workout, exercises, workout_exercises, sets = map_hevy_workout_to_models(hevy_data)

    assert routine.name == "Quick Workout"
    assert workout.title == "Quick Workout"
    assert workout.updated_at is None
    assert len(exercises) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_hevy_mapper.py -v
```

Expected: ImportError for `workout_mcp.hevy_mapper`

- [ ] **Step 3: Implement mapper**

Create `workout_mcp/hevy_mapper.py`:

```python
"""Map Hevy API workout JSON to SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from workout_mcp.models import Exercise, Routine, Set, Workout, WorkoutExercise


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime."""
    if value is None:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def map_hevy_workout_to_models(
    hevy_data: dict[str, Any]
) -> tuple[Routine, Workout, list[Exercise], list[WorkoutExercise], list[Set]]:
    """Transform a Hevy API workout dict into our ORM model instances.

    Returns:
        (routine, workout, exercises, workout_exercises, sets)
    """
    title = hevy_data.get("title") or "Untitled Workout"
    description = hevy_data.get("description")
    start_time = parse_datetime(hevy_data.get("start_time"))
    end_time = parse_datetime(hevy_data.get("end_time"))
    updated_at = parse_datetime(hevy_data.get("updated_at"))
    routine_name = hevy_data.get("routine_name") or title

    routine = Routine(name=routine_name)
    workout = Workout(
        start=start_time,
        end=end_time,
        title=title,
        description=description,
        updated_at=updated_at,
        routine=routine,
    )

    exercises: list[Exercise] = []
    workout_exercises: list[WorkoutExercise] = []
    sets: list[Set] = []

    for exercise_index, exercise_data in enumerate(hevy_data.get("exercises", [])):
        exercise_name = exercise_data.get("title") or "Unknown Exercise"
        exercise = Exercise(name=exercise_name)
        exercises.append(exercise)

        workout_exercise = WorkoutExercise(
            workout=workout,
            exercise=exercise,
            exercise_index=exercise_index,
        )
        workout_exercises.append(workout_exercise)

        for set_data in exercise_data.get("sets", []):
            weight = set_data.get("weight_kg")
            reps = set_data.get("reps")
            rpe = set_data.get("rpe")
            distance_meters = set_data.get("distance_meters")
            duration_seconds = set_data.get("duration_seconds")

            distance_km = distance_meters / 1000.0 if distance_meters is not None else None

            set_ = Set(
                workout_exercise=workout_exercise,
                set_index=set_data.get("set_number", 0),
                reps=reps,
                weight=weight,
                rpe=rpe,
                distance_km=distance_km,
                duration_seconds=duration_seconds,
            )
            sets.append(set_)

    return routine, workout, exercises, workout_exercises, sets
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_hevy_mapper.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/hevy_mapper.py tests/test_hevy_mapper.py
git commit -m "feat: add Hevy API data mapper"
```

---

### Task 6: Create DB sync service

**Files:**
- Create: `workout_mcp/sync_service.py`
- Test: `tests/test_sync_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sync_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

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
                ]
            }
        ]
    }

    upsert_hevy_workout(db_session, hevy_data)

    assert db_session.query(Routine).count() == 1
    assert db_session.query(Workout).count() == 1
    assert db_session.query(Exercise).count() == 1
    assert db_session.query(WorkoutExercise).count() == 1
    assert db_session.query(Set).count() == 1

    routine = db_session.query(Routine).first()
    assert routine.name == "Push Routine"

    workout = db_session.query(Workout).first()
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
                ]
            }
        ]
    }

    upsert_hevy_workout(db_session, hevy_data_v1)
    original_workout_id = db_session.query(Workout).first().id

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
                    }
                ]
            }
        ]
    }

    upsert_hevy_workout(db_session, hevy_data_v2)

    workout = db_session.query(Workout).first()
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
            {
                "title": "Bench Press",
                "sets": [{"set_number": 0, "weight_kg": 100, "reps": 5}]
            }
        ]
    }

    upsert_hevy_workout(db_session, hevy_data)
    exercise_count_after_first = db_session.query(Exercise).count()

    upsert_hevy_workout(db_session, hevy_data)
    exercise_count_after_second = db_session.query(Exercise).count()

    assert exercise_count_after_first == exercise_count_after_second
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_sync_service.py -v
```

Expected: ImportError for `workout_mcp.sync_service`

- [ ] **Step 3: Implement sync service**

Create `workout_mcp/sync_service.py`:

```python
"""Database sync service for Hevy API data."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workout_mcp.hevy_mapper import map_hevy_workout_to_models
from workout_mcp.logging import get_logger
from workout_mcp.models import Exercise, Routine, Workout

logger = get_logger(__name__)


def upsert_hevy_workout(db: Session, hevy_data: dict[str, Any]) -> None:
    """Upsert a Hevy workout into the database.

    Uses existing unique constraints:
    - Routine by name
    - Workout by (routine_id, start, end) — delete and replace on conflict
    - Exercise by name
    """
    routine_model, workout_model, exercises, workout_exercises, sets = (
        map_hevy_workout_to_models(hevy_data)
    )

    # Upsert routine by name
    routine = db.query(Routine).filter_by(name=routine_model.name).first()
    if routine is None:
        routine = Routine(name=routine_model.name)
        db.add(routine)
        db.flush()
        logger.info("routine_created", name=routine.name)
    workout_model.routine = routine

    # Check for existing workout by unique constraint
    existing_workout = (
        db.query(Workout)
        .filter_by(
            routine_id=routine.id,
            start=workout_model.start,
            end=workout_model.end,
        )
        .first()
    )

    if existing_workout is not None:
        db.delete(existing_workout)
        db.flush()
        logger.info(
            "workout_deleted_for_update",
            routine=routine.name,
            start=workout_model.start.isoformat(),
        )

    db.add(workout_model)
    db.flush()

    # Upsert exercises by name
    for exercise_model in exercises:
        exercise = db.query(Exercise).filter_by(name=exercise_model.name).first()
        if exercise is None:
            exercise = Exercise(name=exercise_model.name)
            db.add(exercise)
            db.flush()
            logger.info("exercise_created", name=exercise.name)

    # Update workout_exercise references to use the persisted exercise instances
    for we in workout_exercises:
        exercise_name = we.exercise.name
        persisted_exercise = db.query(Exercise).filter_by(name=exercise_name).first()
        we.exercise = persisted_exercise

    db.add_all(sets)
    db.flush()

    logger.info(
        "workout_upserted",
        title=workout_model.title,
        routine=routine.name,
        exercises=len(exercises),
        sets=len(sets),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_sync_service.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/sync_service.py tests/test_sync_service.py
git commit -m "feat: add DB sync service with delete-and-replace upsert"
```

---

### Task 7: Add webhook endpoint

**Files:**
- Modify: `workout_mcp/api.py`
- Test: `tests/test_webhook.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_webhook.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_webhook_returns_200(client: TestClient) -> None:
    with patch("workout_mcp.api.upsert_hevy_workout") as mock_upsert:
        response = client.post("/webhooks/hevy", json={"workoutId": "test-id-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_upsert.assert_called_once()


def test_webhook_without_api_key_returns_503(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.hevy_api_key", None):
        response = client.post("/webhooks/hevy", json={"workoutId": "test-id-123"})
    assert response.status_code == 503
    assert "Hevy API not configured" in response.json()["detail"]


def test_webhook_invalid_signature_returns_400(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.hevy_webhook_secret", "secret"):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
            headers={"X-Hevy-Signature": "invalid"}
        )
    assert response.status_code == 400
    assert "Invalid signature" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_webhook.py -v
```

Expected: `404` because `/webhooks/hevy` does not exist

- [ ] **Step 3: Add imports and webhook endpoint**

Add imports to `workout_mcp/api.py`:

```python
import hashlib
import hmac

from fastapi import BackgroundTasks

from workout_mcp.config import settings
from workout_mcp.hevy_client import HevyAPIError, HevyClient
from workout_mcp.logging import get_logger
from workout_mcp.sync_service import upsert_hevy_workout
```

Add the webhook endpoint after the existing `/import/csv` endpoint:

```python

def _verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if signature is None:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _process_webhook_workout(workout_id: str) -> None:
    """Background task to fetch and upsert a Hevy workout."""
    logger = get_logger(__name__)
    if not settings.hevy_api_key:
        logger.warning("webhook_skipped_no_api_key")
        return

    try:
        async with HevyClient() as client:
            workout_data = await client.get_workout(workout_id)
    except HevyAPIError as exc:
        logger.error("webhook_fetch_failed", workout_id=workout_id, error=str(exc))
        return

    from workout_mcp.database import SessionLocal

    db = SessionLocal()
    try:
        upsert_hevy_workout(db, workout_data)
        db.commit()
        logger.info("webhook_workout_upserted", workout_id=workout_id)
    except Exception as exc:
        db.rollback()
        logger.error("webhook_upsert_failed", workout_id=workout_id, error=str(exc))
    finally:
        db.close()


@app.post("/webhooks/hevy")
async def hevy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Receive Hevy webhook notifications."""
    body = await request.body()
    data = await request.json()
    workout_id = data.get("workoutId")

    if not workout_id:
        raise HTTPException(status_code=400, detail="Missing workoutId")

    if settings.hevy_webhook_secret:
        signature = request.headers.get("X-Hevy-Signature")
        if not _verify_webhook_signature(body, signature, settings.hevy_webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid signature")

    if not settings.hevy_api_key:
        raise HTTPException(status_code=503, detail="Hevy API not configured")

    background_tasks.add_task(_process_webhook_workout, workout_id)
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_webhook.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/api.py tests/test_webhook.py
git commit -m "feat: add Hevy webhook endpoint with signature verification"
```

---

### Task 8: Create fallback sync job

**Files:**
- Create: `workout_mcp/sync.py`
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sync.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from workout_mcp.models import SyncState, Workout
from workout_mcp.sync import sync_hevy_workouts


@pytest.mark.anyio
async def test_sync_creates_workout_from_event(db_session: Session) -> None:
    mock_events = {
        "events": [
            {
                "type": "updated",
                "workout": {
                    "id": "w1",
                    "title": "Push Day",
                    "description": None,
                    "start_time": "2024-01-01T10:00:00+00:00",
                    "end_time": "2024-01-01T11:00:00+00:00",
                    "updated_at": "2024-01-01T12:00:00+00:00",
                    "routine_name": "Push",
                    "exercises": []
                }
            }
        ]
    }

    with patch("workout_mcp.sync.HevyClient") as MockClient:
        client = AsyncMock()
        client.get_workout_events = AsyncMock(return_value=mock_events)
        client.get_workout = AsyncMock(return_value=mock_events["events"][0]["workout"])
        client.close = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        await sync_hevy_workouts(db_session)

    assert db_session.query(Workout).count() == 1
    workout = db_session.query(Workout).first()
    assert workout.title == "Push Day"

    sync_state = db_session.query(SyncState).first()
    assert sync_state is not None
    assert sync_state.last_sync_at is not None


@pytest.mark.anyio
async def test_sync_no_api_key_skips(db_session: Session) -> None:
    with patch("workout_mcp.sync.settings.hevy_api_key", None):
        await sync_hevy_workouts(db_session)
    assert db_session.query(Workout).count() == 0


@pytest.mark.anyio
async def test_sync_skips_deleted_event(db_session: Session) -> None:
    mock_events = {
        "events": [
            {
                "type": "deleted",
                "workout_id": "w1",
                "deleted_at": "2024-01-02T10:00:00+00:00"
            }
        ]
    }

    with patch("workout_mcp.sync.HevyClient") as MockClient:
        client = AsyncMock()
        client.get_workout_events = AsyncMock(return_value=mock_events)
        client.close = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        await sync_hevy_workouts(db_session)

    # No crash, sync state updated
    sync_state = db_session.query(SyncState).first()
    assert sync_state is not None
    assert sync_state.last_sync_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_sync.py -v
```

Expected: ImportError for `workout_mcp.sync`

- [ ] **Step 3: Implement sync job**

Create `workout_mcp/sync.py`:

```python
"""Fallback sync job for Hevy API workouts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from workout_mcp.config import settings
from workout_mcp.hevy_client import HevyAPIError, HevyClient
from workout_mcp.hevy_mapper import parse_datetime
from workout_mcp.logging import get_logger
from workout_mcp.models import SyncState
from workout_mcp.sync_service import upsert_hevy_workout

logger = get_logger(__name__)


async def sync_hevy_workouts(db: Session) -> None:
    """Poll Hevy API for workout events and sync to local DB."""
    if not settings.hevy_api_key:
        logger.info("sync_skipped_no_api_key")
        return

    sync_state = db.query(SyncState).filter_by(id=1).first()
    if sync_state is None:
        sync_state = SyncState(id=1)
        db.add(sync_state)
        db.flush()

    since = sync_state.last_sync_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
    latest_event_time: datetime | None = None
    total_events = 0

    try:
        async with HevyClient() as client:
            page = 1
            while True:
                response = await client.get_workout_events(since=since, page=page)
                events = response.get("events", [])

                if not events:
                    break

                for event in events:
                    await _process_event(db, client, event)
                    total_events += 1

                    event_time = _extract_event_time(event)
                    if event_time and (latest_event_time is None or event_time > latest_event_time):
                        latest_event_time = event_time

                page += 1

    except HevyAPIError as exc:
        logger.error("sync_api_error", error=str(exc))
        return

    if latest_event_time:
        sync_state.last_sync_at = latest_event_time
    else:
        sync_state.last_sync_at = datetime.now(timezone.utc)
    sync_state.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("sync_completed", events_processed=total_events)


def _extract_event_time(event: dict[str, Any]) -> datetime | None:
    """Extract the most relevant timestamp from an event for watermarking."""
    if event.get("type") == "updated":
        workout = event.get("workout", {})
        ts = workout.get("updated_at")
    elif event.get("type") == "deleted":
        ts = event.get("deleted_at")
    else:
        return None
    if ts:
        return parse_datetime(ts)
    return None


async def _process_event(
    db: Session, client: HevyClient, event: dict[str, Any]
) -> None:
    event_type = event.get("type")

    if event_type == "updated":
        workout_data = event.get("workout")
        if workout_data is None:
            workout_id = event.get("workout_id")
            if workout_id:
                try:
                    workout_data = await client.get_workout(workout_id)
                except HevyAPIError as exc:
                    logger.error("sync_fetch_failed", workout_id=workout_id, error=str(exc))
                    return
            else:
                logger.warning("sync_event_missing_workout_data")
                return

        try:
            upsert_hevy_workout(db, workout_data)
            db.commit()
            logger.info("sync_workout_upserted", title=workout_data.get("title"))
        except Exception as exc:
            db.rollback()
            logger.error("sync_upsert_failed", error=str(exc))

    elif event_type == "deleted":
        # Without hevy_id in DB, we cannot reliably match deleted events to local workouts.
        # Deletion events are logged but skipped. Webhooks handle real-time updates;
        # missing deletions are an acceptable tradeoff for schema simplicity.
        workout_id = event.get("workout_id")
        logger.info("sync_workout_deleted_skipped", workout_id=workout_id)
    else:
        logger.warning("sync_unknown_event_type", event_type=event_type)


def start_scheduler(db_factory: Any) -> AsyncIOScheduler | None:
    """Start the APScheduler with the fallback sync job."""
    if not settings.hevy_api_key:
        logger.info("scheduler_not_started_no_api_key")
        return None

    scheduler = AsyncIOScheduler()
    interval = settings.hevy_sync_interval_minutes

    async def scheduled_sync() -> None:
        db = db_factory()
        try:
            await sync_hevy_workouts(db)
        finally:
            db.close()

    scheduler.add_job(
        scheduled_sync,
        "interval",
        minutes=interval,
        id="hevy_fallback_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler_started", interval_minutes=interval)
    return scheduler
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_sync.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add workout_mcp/sync.py tests/test_sync.py
git commit -m "feat: add fallback sync job with APScheduler"
```

---

### Task 9: Wire scheduler into app lifespan

**Files:**
- Modify: `workout_mcp/api.py`

- [ ] **Step 1: Add lifespan context manager**

Modify `workout_mcp/api.py` to add app lifespan for scheduler startup/shutdown. Add imports at the top:

```python
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from workout_mcp.database import SessionLocal
from workout_mcp.sync import start_scheduler
```

Replace the existing `app = FastAPI(...)` line with:

```python

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler(SessionLocal)
    yield
    if scheduler is not None:
        scheduler.shutdown()

app = FastAPI(title="Workout MCP Server", lifespan=lifespan)
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
pytest tests/test_api.py -v
```

Expected: All existing tests PASS (scheduler won't start because no HEVY_API_KEY in test env)

- [ ] **Step 3: Commit**

```bash
git add workout_mcp/api.py
git commit -m "feat: wire APScheduler into FastAPI lifespan"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- Hevy API configuration: Task 2
- Database schema changes (sync_state + workout fields): Task 3
- HevyClient with error handling: Task 4
- Data mapper (Hevy JSON → ORM): Task 5
- DB upsert with delete-and-replace: Task 6
- Webhook endpoint with signature verification: Task 7
- Fallback sync job with watermark: Task 8
- Scheduler wired into app lifespan: Task 9
- All spec requirements covered.

**2. Placeholder scan:** No TBD, TODO, "implement later", or vague steps found.

**3. Type consistency:** `parse_datetime` is public in `hevy_mapper.py` and imported by `sync.py`. `start_scheduler` returns `AsyncIOScheduler | None`. All model fields match spec.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-23-autosync.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach do you prefer?**
