from __future__ import annotations

from typing import Any

from bson import ObjectId

from services.attendance_merge import merge_attendance_records
from utils.db import get_collection
from utils.db_schema_crud import get_attendance_by_event, get_cadets_by_ids, get_users_by_ids
from utils.names import format_full_name
from utils.pagination import build_pagination_metadata, paginate_list


def build_commander_roster(
    flight_cadets: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Records are expected to be pre-filtered by event in the calling page.
    # If duplicates exist for a cadet (e.g., multiple submissions), merge
    # deterministically before building the roster.
    records = merge_attendance_records(records, key_fields=("cadet_id",))
    record_by_cadet: dict[Any, dict[str, Any]] = {
        r["cadet_id"]: r for r in records if "cadet_id" in r
    }

    roster = []
    for cadet in flight_cadets:
        record = record_by_cadet.get(cadet["_id"])
        roster.append(
            {
                "cadet": cadet,
                "record": record,
                "current_status": record.get("status") if record else None,
            }
        )

    roster.sort(
        key=lambda e: (
            str(e["cadet"].get("name", "") or "").lower(),
            str(e["cadet"].get("last_name", "") or "").lower(),
            str(e["cadet"].get("first_name", "") or "").lower(),
        )
    )
    return roster


def hydrate_cadet_names(
    cadets: list[dict[str, Any]],
    users_by_id: dict[Any, dict[str, Any]],
) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for cadet in cadets:
        user_doc = users_by_id.get(cadet.get("user_id"))
        if user_doc is None:
            hydrated.append(cadet)
            continue

        full_name = format_full_name(user_doc)
        if not full_name:
            hydrated.append(cadet)
            continue

        hydrated_cadet = dict(cadet)
        hydrated_cadet["name"] = full_name
        hydrated.append(hydrated_cadet)

    return hydrated


def compute_upserts(
    roster: list[dict[str, Any]],
    new_statuses: dict[str, str],
) -> list[dict[str, Any]]:
    upserts = []
    for entry in roster:
        cadet_id = entry["cadet"]["_id"]
        new_status = new_statuses.get(str(cadet_id))
        if new_status is None:
            continue

        record = entry["record"]
        if record is not None:
            if entry.get("current_status") == new_status:
                continue
            upserts.append(
                {
                    "action": "update",
                    "cadet_id": cadet_id,
                    "record_id": record["_id"],
                    "status": new_status,
                }
            )
        else:
            upserts.append(
                {
                    "action": "create",
                    "cadet_id": cadet_id,
                    "record_id": None,
                    "status": new_status,
                }
            )
    return upserts


def get_attendance_by_event_for_cadets(
    event_id: str,
    cadet_ids: list[Any],
) -> list[dict[str, Any]]:
    if not cadet_ids:
        return []

    col = get_collection("attendance_records")
    if col is None:
        return []

    if hasattr(col, "find"):
        try:
            return list(
                col.find(
                    {
                        "event_id": ObjectId(event_id),
                        "cadet_id": {"$in": [ObjectId(cadet_id) for cadet_id in cadet_ids]},
                    }
                )
            )
        except Exception:
            pass

    return [
        record
        for record in get_attendance_by_event(event_id)
        if record.get("cadet_id") in cadet_ids
    ]


def _paged_cadet_docs(page: int, page_size: int) -> dict[str, Any]:
    col = get_collection("cadets")
    if col is None:
        return {
            "items": [],
            **build_pagination_metadata(page=page, page_size=page_size, total_count=0),
        }

    if hasattr(col, "count_documents"):
        total_count = int(col.count_documents({}))
        pagination = build_pagination_metadata(
            page=page,
            page_size=page_size,
            total_count=total_count,
        )
        cursor = col.find({})
        if hasattr(cursor, "sort"):
            try:
                cursor = cursor.sort(
                    [
                        ("last_name", 1),
                        ("first_name", 1),
                        ("_id", 1),
                    ]
                )
                if pagination["skip"] > 0:
                    cursor = cursor.skip(pagination["skip"])
                if pagination["page_size"] > 0:
                    cursor = cursor.limit(pagination["page_size"])
                return {**pagination, "items": list(cursor)}
            except TypeError:
                pass

    docs = list(col.find({}))
    docs.sort(
        key=lambda cadet: (
            str(cadet.get("last_name", "") or "").lower(),
            str(cadet.get("first_name", "") or "").lower(),
            str(cadet.get("_id", "") or ""),
        )
    )
    return paginate_list(docs, page=page, page_size=page_size)


def get_paginated_commander_roster(
    event_id: str,
    *,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    cadets_page = _paged_cadet_docs(page, page_size)
    cadets = list(cadets_page["items"])
    if not cadets:
        return {**cadets_page, "items": []}

    cadet_user_ids = [cadet.get("user_id") for cadet in cadets if cadet.get("user_id") is not None]
    users_by_id = {user["_id"]: user for user in get_users_by_ids(cadet_user_ids)}
    hydrated_cadets = hydrate_cadet_names(cadets, users_by_id)

    cadet_ids = [cadet.get("_id") for cadet in hydrated_cadets if cadet.get("_id") is not None]
    records = get_attendance_by_event_for_cadets(event_id, cadet_ids)

    return {**cadets_page, "items": build_commander_roster(hydrated_cadets, records)}


def get_roster_entries_for_cadet_ids(
    event_id: str,
    cadet_ids: list[str],
) -> list[dict[str, Any]]:
    if not cadet_ids:
        return []

    cadets = get_cadets_by_ids(cadet_ids)
    if not cadets:
        return []

    cadet_user_ids = [cadet.get("user_id") for cadet in cadets if cadet.get("user_id") is not None]
    users_by_id = {user["_id"]: user for user in get_users_by_ids(cadet_user_ids)}
    hydrated_cadets = hydrate_cadet_names(cadets, users_by_id)
    records = get_attendance_by_event_for_cadets(
        event_id,
        [cadet.get("_id") for cadet in hydrated_cadets if cadet.get("_id") is not None],
    )
    return build_commander_roster(hydrated_cadets, records)
