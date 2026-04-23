from __future__ import annotations

from typing import Any

from services.attendance_merge import merge_attendance_records
from utils.names import format_full_name


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
