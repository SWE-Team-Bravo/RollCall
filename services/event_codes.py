from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from utils.db_schema_crud import (
    create_event_code,
    deactivate_event_code,
    find_active_event_code_by_value,
    get_active_event_code,
)


def generate_code() -> str:
    """Generate a random 6-digit numeric code."""
    return f"{secrets.randbelow(1000000):06}"


def build_expires_at(exp_date: date, exp_time: time, tz_name: str) -> datetime:
    """Combine a local date and time with a named timezone and return a UTC datetime."""
    tz = ZoneInfo(tz_name)
    local_dt = datetime.combine(exp_date, exp_time).replace(tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def is_expiry_valid(expires_at: datetime) -> bool:
    """Return True if expires_at is strictly in the future (UTC)."""
    return expires_at > datetime.now(timezone.utc)


def create_code(
    event_id: str | ObjectId,
    event_type: str,
    event_date: str,
    created_by_user_id: str | ObjectId,
    expires_at: datetime,
) -> dict | None:
    """Generate and store a new event code, soft-deleting any existing active one."""
    code = generate_code()
    result = create_event_code(
        code=code,
        event_id=event_id,
        event_type=event_type,
        event_date=event_date,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    if result is None:
        return None
    return {
        "_id": result.inserted_id,
        "code": code,
        "expires_at": expires_at,
    }


def get_active_code(event_id: str | ObjectId) -> dict | None:
    return get_active_event_code(event_id)


def expire_code(code_id: str | ObjectId) -> bool:
    """Manually deactivate a code. Returns True on success."""
    result = deactivate_event_code(code_id)
    return result is not None and result.modified_count == 1


def validate_code(code: str) -> dict | None:
    code = code.replace(" ", "")
    return find_active_event_code_by_value(code)


def expires_at_from_preset(preset: str) -> datetime:
    """Convert a preset label to an absolute UTC expiry datetime."""
    now = datetime.now(timezone.utc)
    presets = {
        "15 minutes": timedelta(minutes=15),
        "30 minutes": timedelta(minutes=30),
        "1 hour": timedelta(hours=1),
        "end of day": None,
    }
    delta = presets.get(preset)
    if delta is not None:
        return now + delta
    return now.replace(hour=23, minute=59, second=59, microsecond=0)
