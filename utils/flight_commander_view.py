from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_active_event(event: dict[str, Any], now: datetime) -> bool:
    start = event.get("start_date")
    end = event.get("end_date")
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return False

    start = _ensure_utc(start)
    end = _ensure_utc(end)
    now = _ensure_utc(now)

    return start <= now <= end


def _checked_in_status(status: str | None) -> bool:
    normalized = (status or "").lower()
    return normalized in {"present", "excused"}


def get_active_events(
    events: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    now = _ensure_utc(now)
    return [event for event in events if _is_active_event(event, now)]


def build_checkin_view(
    flight_cadets: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
    attendance_records: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    event: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a view of checked-in vs missing cadets for an event.

    Two usage patterns are supported:

    1. Time-based active event selection (existing behavior)
       - Provide ``events`` and ``now``; the first active event is chosen.

    2. Explicit event selection (used by tests)
       - Provide ``event`` directly; no date filtering is applied and the
         event is used as-is, which allows events without start/end dates.
    """

    attendance_records = attendance_records or []

    # If an explicit event is provided, use it directly without
    # checking time windows. This matches the expectations in
    # test_selected_event_changes_output.
    if event is not None:
        active_event = event
    else:
        # Fallback to existing behavior: pick the first active event
        # from the provided list, based on the current time.
        if events is None or now is None:
            return None

        now = _ensure_utc(now)
        active_event = next((e for e in events if _is_active_event(e, now)), None)
        if active_event is None:
            return None

    active_event_id = active_event.get("_id")
    if active_event_id is None:
        return None

    checked_in_ids = {
        record["cadet_id"]
        for record in attendance_records
        if record.get("event_id") == active_event_id
        and _checked_in_status(record.get("status"))
    }

    checked_in: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for cadet in flight_cadets:
        if cadet.get("_id") in checked_in_ids:
            checked_in.append(cadet)
        else:
            missing.append(cadet)

    return {
        "event": active_event,
        "checked_in": checked_in,
        "missing": missing,
    }
