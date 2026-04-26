import math
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
    checkin_close = start + timedelta(minutes=window_minutes)
    return checkin_open <= now <= checkin_close


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def is_within_geofence(event: dict, lat: float, lon: float) -> tuple[bool, str]:
    """Return (within_fence, warning_message). Empty message means within fence."""
    if not event.get("geofence_enabled"):
        return True, ""
    fence_lat = event.get("geofence_lat")
    fence_lon = event.get("geofence_lon")
    if fence_lat is None or fence_lon is None:
        return True, ""
    radius = event.get("geofence_radius_meters", 150)
    dist = _haversine_meters(lat, lon, fence_lat, fence_lon)
    if dist <= radius:
        return True, ""
    return (
        False,
        f"You appear to be {int(dist)}m from the event location (limit: {int(radius)}m).",
    )
