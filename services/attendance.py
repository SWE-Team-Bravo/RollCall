import secrets
from typing import Any
from datetime import datetime, timedelta, timezone

from services.event_config import get_checkin_window_minutes

CHECKIN_WINDOW_MINUTES = 10  # fallback used by tests and legacy imports


def generate_attendance_password() -> str:
    """Generate a random 6-digit numeric attendance password."""
    return f"{secrets.randbelow(1000000):06}"


def is_already_checked_in(
    event_id: str,
    cadet_id: str,
    existing_records: list[dict],
) -> bool:
    return any(
        str(r.get("event_id")) == str(event_id)
        and str(r.get("cadet_id")) == str(cadet_id)
        for r in existing_records
    )


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_within_checkin_window(
    event: dict[str, Any],
    now: datetime,
    *,
    window_minutes: int | None = None,
) -> bool:
    start = event.get("start_date")
    if not isinstance(start, datetime):
        return False

    start = _ensure_utc(start)
    now = _ensure_utc(now)

    minutes = window_minutes if window_minutes is not None else get_checkin_window_minutes()
    checkin_open = start - timedelta(minutes=minutes)
    return checkin_open <= now <= start
