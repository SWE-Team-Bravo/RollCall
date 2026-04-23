from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from bson import ObjectId

from utils.db import get_db
from utils.datetime_utils import ensure_utc


_PREFERRED_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
]


def get_timezone_options() -> list[str]:
    return _PREFERRED_TIMEZONES + [
        tz for tz in sorted(available_timezones()) if tz not in _PREFERRED_TIMEZONES
    ]


def build_event_bounds(
    start_date: date,
    end_date: date,
    tz_name: str = "UTC",
) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    local_start = datetime.combine(start_date, time.min, tzinfo=tz)
    local_end = datetime.combine(end_date, time(23, 59, 59), tzinfo=tz)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _is_legacy_all_day_bounds(start_at: datetime, end_at: datetime) -> bool:
    start_utc = ensure_utc(start_at)
    end_utc = ensure_utc(end_at)
    return (
        start_utc.hour == 0
        and start_utc.minute == 0
        and start_utc.second == 0
        and start_utc.microsecond == 0
        and end_utc.hour == 23
        and end_utc.minute == 59
        and end_utc.second == 59
    )


def get_event_time_bounds(
    event: dict[str, Any] | None,
    *,
    fallback_tz_name: str | None = None,
) -> tuple[datetime | None, datetime | None]:
    if not event:
        return None, None

    start_at = event.get("start_date")
    end_at = event.get("end_date") or start_at
    if not isinstance(start_at, datetime) or not isinstance(end_at, datetime):
        return None, None

    if (
        fallback_tz_name
        and not event.get("timezone_name")
        and _is_legacy_all_day_bounds(start_at, end_at)
    ):
        return build_event_bounds(
            ensure_utc(start_at).date(),
            ensure_utc(end_at).date(),
            fallback_tz_name,
        )

    return ensure_utc(start_at), ensure_utc(end_at)


def closest_event_index(events: list[dict]) -> int:
    if not events:
        return 0
    today = date.today()

    def _distance(event: dict) -> int:
        start = event.get("start_date")
        try:
            if isinstance(start, datetime):
                return abs((start.date() - today).days)
            return abs((date.fromisoformat(str(start)[:10]) - today).days)
        except ValueError:
            return 999_999

    return min(range(len(events)), key=lambda i: _distance(events[i]))


def has_event_ended(
    event: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> bool:
    _, end_at = get_event_time_bounds(event)
    if end_at is None:
        return False

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    return current_time > end_at


def get_all_events() -> list[dict]:
    """Return all events sorted by start date descending."""
    db = get_db()
    if db is None:
        return []
    events = list(db.events.find({}).sort("start_date", -1))
    for e in events:
        e["_id"] = str(e["_id"])
    return events


def create_event(
    name: str,
    event_type: str,
    start_date: date,
    end_date: date,
    created_by_user_id: str,
    tz_name: str = "UTC",
) -> bool:
    """Insert a new event. Returns True on success."""
    if start_date > end_date:
        return False
    db = get_db()
    if db is None:
        return False
    start_dt, end_dt = build_event_bounds(start_date, end_date, tz_name)
    db.events.insert_one(
        {
            "event_name": name,
            "event_type": event_type,
            "start_date": start_dt,
            "end_date": end_dt,
            "timezone_name": tz_name,
            "created_by_user_id": created_by_user_id,
        }
    )
    return True


def delete_event(event_id: str) -> bool:
    """Delete an event by its string ID. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    result = db.events.delete_one({"_id": ObjectId(event_id)})
    return result.deleted_count == 1
