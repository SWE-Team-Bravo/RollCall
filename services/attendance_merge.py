from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

try:
    from bson import ObjectId
except Exception:  # pragma: no cover
    ObjectId = None  # type: ignore


_HIGH_PRIORITY_ROLES = {"admin", "cadre", "flight_commander"}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _record_time(record: dict[str, Any]) -> datetime:
    dt = record.get("updated_at") or record.get("created_at")
    if isinstance(dt, datetime):
        return _as_utc(dt)

    _id = record.get("_id")
    if ObjectId is not None and isinstance(_id, ObjectId):
        # generation_time is timezone-aware UTC
        return _id.generation_time

    return datetime.min.replace(tzinfo=timezone.utc)


def _role_priority(record: dict[str, Any]) -> int:
    roles = record.get("recorded_by_roles")
    if not isinstance(roles, Iterable) or isinstance(roles, (str, bytes)):
        return 0

    normalized = {str(r).strip().lower() for r in roles}
    return 2 if (normalized & _HIGH_PRIORITY_ROLES) else 1


def _pick_best_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    # Higher role priority wins; then newest timestamp.
    return max(records, key=lambda r: (_role_priority(r), _record_time(r)))


def merge_attendance_records(
    records: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...] = ("event_id", "cadet_id"),
) -> list[dict[str, Any]]:
    """Merge duplicate attendance records deterministically.

    Groups records by the given key_fields and selects a single 'best' record
    per group.

    Selection rule:
    1) Records written by higher-privilege roles win (admin/cadre/flight_commander)
       when the record includes `recorded_by_roles`.
    2) Ties break by newest `updated_at`/`created_at` (falling back to ObjectId time).

    If `recorded_by_roles` is missing on records, the merge falls back to time only.
    """

    if not records:
        return []

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(record.get(f) for f in key_fields)
        grouped.setdefault(key, []).append(record)

    merged = [_pick_best_record(group) for group in grouped.values()]
    merged.sort(key=_record_time, reverse=True)
    return merged
