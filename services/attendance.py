import secrets
from typing import Any
from datetime import datetime, timedelta, timezone


CHECKIN_WINDOW_MINUTES = 10


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


def is_within_checkin_window(event: dict[str, Any], now: datetime) -> bool:
    start = event.get("start_date")
    if not isinstance(start, datetime):
        return False

    start = _ensure_utc(start)
    now = _ensure_utc(now)

    checkin_open = start - timedelta(minutes=CHECKIN_WINDOW_MINUTES)
    return checkin_open <= now <= start
