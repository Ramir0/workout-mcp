from __future__ import annotations

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
                    "exercises": [],
                },
            }
        ]
    }

    with (
        patch("workout_mcp.sync.HevyClient") as mock_client_cls,
        patch("workout_mcp.sync.settings.hevy_api_key", "test-api-key"),
    ):
        client = AsyncMock()
        client.get_workout_events = AsyncMock(side_effect=[mock_events, {"events": []}])
        client.get_workout = AsyncMock(return_value=mock_events["events"][0]["workout"])
        client.close = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await sync_hevy_workouts(db_session)

    assert db_session.query(Workout).count() == 1
    workout = db_session.query(Workout).first()
    assert workout is not None
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
            {"type": "deleted", "workout_id": "w1", "deleted_at": "2024-01-02T10:00:00+00:00"}
        ]
    }

    with (
        patch("workout_mcp.sync.HevyClient") as mock_client_cls,
        patch("workout_mcp.sync.settings.hevy_api_key", "test-api-key"),
    ):
        client = AsyncMock()
        client.get_workout_events = AsyncMock(side_effect=[mock_events, {"events": []}])
        client.close = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await sync_hevy_workouts(db_session)

    # No crash, sync state updated
    sync_state = db_session.query(SyncState).first()
    assert sync_state is not None
    assert sync_state.last_sync_at is not None
