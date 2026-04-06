from __future__ import annotations

from typing import Any


def build_commander_roster(
    flight_cadets: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
            str(e["cadet"].get("last_name", "") or "").lower(),
            str(e["cadet"].get("first_name", "") or "").lower(),
        )
    )
    return roster


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
