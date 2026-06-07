"""Hevy sync — incremental polling of workout events."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from workout_mcp.config import settings
from workout_mcp.hevy_client import HevyAPIError, HevyClient
from workout_mcp.hevy_mapper import parse_datetime
from workout_mcp.logging import get_logger
from workout_mcp.models import SyncState
from workout_mcp.sync_service import upsert_hevy_workout

logger = get_logger(__name__)


async def trigger_sync(
    db_factory: Callable[[], Session],
) -> None:
    """Poll Hevy API for recent workout events and sync to local DB."""
    db = db_factory()
    try:
        await sync_hevy_workouts(db)
    finally:
        db.close()


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

    since = sync_state.last_sync_at or datetime(2024, 1, 1, tzinfo=UTC)
    latest_event_time: datetime | None = None
    total_events = 0

    try:
        async with HevyClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get_workout_events(since=since, page=page)
                except HevyAPIError as exc:
                    if exc.status_code == 404:
                        break
                    raise

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
        logger.error(
            "sync_api_error",
            error=str(exc),
            page=page,
            since=since.isoformat(),
            url=exc.url,
            method=exc.method,
            params=exc.params,
            status_code=exc.status_code,
            response_text=exc.response_text,
        )
        return

    if latest_event_time:
        sync_state.last_sync_at = latest_event_time
    else:
        sync_state.last_sync_at = datetime.now(UTC)
    sync_state.updated_at = datetime.now(UTC)
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


async def _process_event(db: Session, client: HevyClient, event: dict[str, Any]) -> None:
    event_type = event.get("type")

    if event_type == "updated":
        workout_data = event.get("workout")
        if workout_data is None:
            workout_id = event.get("workout_id")
            if workout_id:
                try:
                    workout_data = await client.get_workout(workout_id)
                except HevyAPIError as exc:
                    logger.error(
                        "sync_fetch_failed",
                        workout_id=workout_id,
                        error=str(exc),
                        url=exc.url,
                        method=exc.method,
                        params=exc.params,
                        status_code=exc.status_code,
                        response_text=exc.response_text,
                    )
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
