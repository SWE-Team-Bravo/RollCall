from datetime import date
from bson import ObjectId
from utils.db import get_db


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
    db.events.insert_one({
        "event_name": name,
        "event_type": event_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "created_by_user_id": created_by_user_id,
    })
    return True


def delete_event(event_id: str) -> bool:
    """Delete an event by its string ID. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    result = db.events.delete_one({"_id": ObjectId(event_id)})
    return result.deleted_count == 1