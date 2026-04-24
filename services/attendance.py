import secrets
from typing import Any
from datetime import datetime, timedelta

from utils.datetime_utils import ensure_utc
from services.event_config import get_checkin_window_minutes


CHECKIN_WINDOW_MINUTES = get_checkin_window_minutes()


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


def is_within_checkin_window(
    event: dict[str, Any],
    now: datetime,
    window_minutes: int = CHECKIN_WINDOW_MINUTES,
) -> bool:
    start = event.get("start_date")
    if not isinstance(start, datetime):
        return False

    start = ensure_utc(start)
    now = ensure_utc(now)

    checkin_open = start - timedelta(minutes=window_minutes)
    return checkin_open <= now <= start
