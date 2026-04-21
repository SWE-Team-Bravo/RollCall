from datetime import date, datetime, timezone
from typing import Any
from bson import ObjectId
from utils.db import get_db


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
        except (ValueError, TypeError):
            return 999_999

    return min(range(len(events)), key=lambda i: _distance(events[i]))


def has_event_ended(
    event: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not event:
        return False

    end_at = event.get("end_date") or event.get("start_date")
    if not isinstance(end_at, datetime):
        return False

    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)

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
) -> bool:
    """Insert a new event. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    start_dt = datetime(
        start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
    )
    end_dt = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc
    )
    db.events.insert_one(
        {
            "event_name": name,
            "event_type": event_type,
            "start_date": start_dt,
            "end_date": end_dt,
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
