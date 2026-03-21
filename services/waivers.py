from datetime import datetime, timezone

from utils.db_schema_crud import (
    create_waiver_approval,
    update_waiver,
    validate_waiver,
    delete_waiver,
)


def get_all_waivers_for_cadet(
    records: list[dict],
    waivers_by_record_id: dict,
    events_by_id: dict,
) -> list[dict]:
    """Return all waivers for a cadet, enriched with event name and date."""
    result = []
    for record in records:
        waiver = waivers_by_record_id.get(record["_id"])
        if not waiver:
            continue
        waiver = dict(waiver)
        event = events_by_id.get(record.get("event_id"))
        waiver["_event_name"] = (
            event.get("event_name") if event else "Unknown event"
        )
        start_date = event.get("start_date") if event else None
        waiver["_event_date"] = (
            start_date.strftime("%Y-%m-%d") if start_date else "Unknown date"
        )
        result.append(waiver)

    return result


def get_absent_records_without_waiver(
    records: list[dict],
    waivers_by_record_id: dict,
) -> list[dict]:
    """Return absent attendance records that are eligible for a new waiver submission.

    Includes records with no waiver, and records whose only waiver was auto-denied
    (allowing resubmission).
    """
    absent = [r for r in records if r.get("status") == "absent"]
    eligible = []
    for record in absent:
        existing = waivers_by_record_id.get(record["_id"])
        if not existing:
            eligible.append(record)
        else:
            status = (existing.get("status") or "").lower()
            auto_denied = bool(existing.get("auto_denied"))
            if status == "denied" and auto_denied:
                eligible.append(record)
    return eligible


def resubmit_auto_denied_waiver(
    existing_waiver: dict, record_id, reason: str
) -> tuple[bool, str]:
    """Attempt to resubmit an auto-denied waiver with a new reason.

    Returns (became_pending, message).
    - If still invalid: waiver stays denied, returns (False, why).
    - If now valid: waiver reset to pending, returns (True, "").
    """
    is_valid, why = validate_waiver(record_id)

    if not is_valid:
        update_waiver(
            existing_waiver["_id"],
            {
                "reason": reason,
                "status": "denied",
                "auto_denied": True,
                "created_at": datetime.now(timezone.utc),
            },
        )
        create_waiver_approval(
            waiver_id=existing_waiver["_id"],
            approver_id=None,
            decision="denied",
            comments=f"Auto-denied (resubmit): {why}",
        )
        return False, why

    update_waiver(
        existing_waiver["_id"],
        {
            "reason": reason,
            "status": "pending",
            "auto_denied": False,
            "created_at": datetime.now(timezone.utc),
        },
    )
    create_waiver_approval(
        waiver_id=existing_waiver["_id"],
        approver_id=None,
        decision="pending",
        comments="Resubmitted successfully.",
    )
    return True, ""


def withdraw_waiver(waiver_id: str) -> bool:
    """Delete pending waiver. Returns True on success"""
    result = delete_waiver(waiver_id)
    return bool(result and result.deleted_count > 0)
