from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from bson import ObjectId

from utils.audit_log import log_data_change, serialize_doc_for_audit
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


def _coerce_object_id_or_raw(value: str | ObjectId | None) -> str | ObjectId | None:
    if value is None or isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except Exception:
        return value


def _active_event_query(*, include_archived: bool) -> dict[str, Any]:
    if include_archived:
        return {}
    return {"archived": {"$ne": True}}


def get_timezone_options() -> list[str]:
    return _PREFERRED_TIMEZONES + [
        tz for tz in sorted(available_timezones()) if tz not in _PREFERRED_TIMEZONES
    ]


def build_event_bounds(
    start_date: date,
    end_date: date,
    tz_name: str = "UTC",
    start_time: time = time.min,
    end_time: time = time(23, 59, 59),
) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    local_start = datetime.combine(start_date, start_time, tzinfo=tz)
    local_end = datetime.combine(end_date, end_time, tzinfo=tz)
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


def _format_event_dt(event: dict, field: str = "start_date") -> str:
    """Return a human-readable datetime string in the event's local timezone."""
    dt = event.get(field)
    if not isinstance(dt, datetime):
        return "—"
    tz_name = event.get("timezone_name", "UTC")
    try:
        local = ensure_utc(dt).astimezone(ZoneInfo(tz_name))
    except Exception:
        local = ensure_utc(dt)
    return local.strftime("%Y-%m-%d %H:%M %Z")


def get_all_events(*, include_archived: bool = False) -> list[dict]:
    """Return all events sorted by start date descending."""
    db = get_db()
    if db is None:
        return []
    events = list(
        db.events.find(_active_event_query(include_archived=include_archived)).sort(
            "start_date", -1
        )
    )
    for e in events:
        e["_id"] = str(e["_id"])
        e["_display_start"] = _format_event_dt(e, "start_date")
        e["_display_end"] = _format_event_dt(e, "end_date")
    return events


def create_event(
    name: str,
    event_type: str,
    start_date: date,
    end_date: date,
    created_by_user_id: str,
    tz_name: str = "UTC",
    geofence_enabled: bool = False,
    geofence_lat: float | None = None,
    geofence_lon: float | None = None,
    geofence_radius_meters: int = 150,
    start_time: time = time.min,
    end_time: time = time(23, 59, 59),
    *,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
) -> bool:
    """Insert a new event. Returns True on success."""
    if start_date > end_date:
        return False
    db = get_db()
    if db is None:
        return False
    start_dt, end_dt = build_event_bounds(
        start_date, end_date, tz_name, start_time, end_time
    )
    event_doc = {
        "event_name": name,
        "event_type": event_type,
        "start_date": start_dt,
        "end_date": end_dt,
        "timezone_name": tz_name,
        "created_by_user_id": _coerce_object_id_or_raw(created_by_user_id),
        "archived": False,
        "created_at": datetime.now(timezone.utc),
        "geofence_enabled": geofence_enabled,
        "geofence_lat": geofence_lat if geofence_enabled else None,
        "geofence_lon": geofence_lon if geofence_enabled else None,
        "geofence_radius_meters": geofence_radius_meters if geofence_enabled else None,
    }
    result = db.events.insert_one(event_doc)
    inserted = db.events.find_one({"_id": result.inserted_id})
    log_data_change(
        source="event_management",
        action="create",
        target_collection="events",
        target_id=result.inserted_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_label=name,
        before=None,
        after=serialize_doc_for_audit(inserted),
        metadata={"event_type": event_type},
    )
    return True


def bulk_create_events(
    semester_start: date,
    semester_end: date,
    pt_days: list[str],
    llab_days: list[str],
    pt_start_time: time,
    pt_end_time: time,
    llab_start_time: time,
    llab_end_time: time,
    tz_name: str,
    skip_dates: list[date],
    created_by_user_id: str,
    *,
    geofence_enabled: bool = False,
    geofence_lat: float | None = None,
    geofence_lon: float | None = None,
    geofence_radius_meters: int = 150,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
) -> tuple[int, int]:
    """Bulk-create PT and LLAB events for a semester date range.

    Returns (created_count, skipped_count).
    """
    skip_set = set(skip_dates)
    created = 0
    skipped = 0
    current = semester_start
    while current <= semester_end:
        day_name = current.strftime("%A")
        if day_name in pt_days:
            if current in skip_set:
                skipped += 1
            else:
                label = current.strftime("%a %b %d %Y")
                ok = create_event(
                    f"PT {label}",
                    "pt",
                    current,
                    current,
                    created_by_user_id,
                    tz_name,
                    geofence_enabled,
                    geofence_lat,
                    geofence_lon,
                    geofence_radius_meters,
                    start_time=pt_start_time,
                    end_time=pt_end_time,
                    actor_user_id=actor_user_id,
                    actor_email=actor_email,
                )
                if ok:
                    created += 1
        elif day_name in llab_days:
            if current in skip_set:
                skipped += 1
            else:
                label = current.strftime("%a %b %d %Y")
                ok = create_event(
                    f"LLAB {label}",
                    "lab",
                    current,
                    current,
                    created_by_user_id,
                    tz_name,
                    geofence_enabled,
                    geofence_lat,
                    geofence_lon,
                    geofence_radius_meters,
                    start_time=llab_start_time,
                    end_time=llab_end_time,
                    actor_user_id=actor_user_id,
                    actor_email=actor_email,
                )
                if ok:
                    created += 1
        current += timedelta(days=1)
    return created, skipped


def preview_semester_schedule(
    semester_start: date,
    semester_end: date,
    pt_days: list[str],
    llab_days: list[str],
    skip_dates: list[date],
) -> list[dict]:
    """Return a list of events that would be created (no DB writes)."""
    skip_set = set(skip_dates)
    events = []
    current = semester_start
    while current <= semester_end:
        day_name = current.strftime("%A")
        if current not in skip_set:
            if day_name in pt_days:
                events.append({"date": current, "type": "PT", "day": day_name})
            elif day_name in llab_days:
                events.append({"date": current, "type": "LLAB", "day": day_name})
        current += timedelta(days=1)
    return events


def archive_event(
    event_id: str,
    *,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
) -> bool:
    """Archive an event by its string ID. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    object_id = ObjectId(event_id)
    before = db.events.find_one({"_id": object_id})
    if before is None:
        return False
    archived_by = _coerce_object_id_or_raw(actor_user_id)
    result = db.events.update_one(
        {"_id": object_id, "archived": {"$ne": True}},
        {
            "$set": {
                "archived": True,
                "archived_at": datetime.now(timezone.utc),
                "archived_by_user_id": archived_by,
            }
        },
    )
    if result.modified_count != 1:
        return False
    after = db.events.find_one({"_id": object_id})
    log_data_change(
        source="event_management",
        action="archive",
        target_collection="events",
        target_id=object_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_label=str(before.get("event_name", "") or "Event"),
        before=serialize_doc_for_audit(before),
        after=serialize_doc_for_audit(after),
    )
    return True


def restore_event(
    event_id: str,
    *,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
) -> bool:
    db = get_db()
    if db is None:
        return False
    object_id = ObjectId(event_id)
    before = db.events.find_one({"_id": object_id})
    if before is None:
        return False
    result = db.events.update_one(
        {"_id": object_id, "archived": True},
        {
            "$set": {
                "archived": False,
                "restored_at": datetime.now(timezone.utc),
                "restored_by_user_id": _coerce_object_id_or_raw(actor_user_id),
            },
            "$unset": {
                "archived_at": "",
                "archived_by_user_id": "",
            },
        },
    )
    if result.modified_count != 1:
        return False
    after = db.events.find_one({"_id": object_id})
    log_data_change(
        source="event_management",
        action="restore",
        target_collection="events",
        target_id=object_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_label=str(before.get("event_name", "") or "Event"),
        before=serialize_doc_for_audit(before),
        after=serialize_doc_for_audit(after),
    )
    return True


def update_event(
    event_id: str,
    name: str,
    event_type: str,
    start_date: date,
    end_date: date,
    tz_name: str = "UTC",
    geofence_enabled: bool = False,
    geofence_lat: float | None = None,
    geofence_lon: float | None = None,
    geofence_radius_meters: int = 150,
    start_time: time = time.min,
    end_time: time = time(23, 59, 59),
    *,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
) -> bool:
    """Update an existing event. Returns True on success."""
    if start_date > end_date:
        return False
    db = get_db()
    if db is None:
        return False
    start_dt, end_dt = build_event_bounds(
        start_date, end_date, tz_name, start_time, end_time
    )
    object_id = ObjectId(event_id)
    before = db.events.find_one({"_id": object_id})
    if before is None:
        return False
    result = db.events.update_one(
        {"_id": object_id},
        {
            "$set": {
                "event_name": name,
                "event_type": event_type,
                "start_date": start_dt,
                "end_date": end_dt,
                "timezone_name": tz_name,
                "geofence_enabled": geofence_enabled,
                "geofence_lat": geofence_lat if geofence_enabled else None,
                "geofence_lon": geofence_lon if geofence_enabled else None,
                "geofence_radius_meters": geofence_radius_meters
                if geofence_enabled
                else None,
            }
        },
    )
    if result.matched_count == 1 and result.modified_count == 1:
        after = db.events.find_one({"_id": object_id})
        log_data_change(
            source="event_management",
            action="update",
            target_collection="events",
            target_id=object_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            target_label=name,
            before=serialize_doc_for_audit(before),
            after=serialize_doc_for_audit(after),
        )
    return result.matched_count == 1
