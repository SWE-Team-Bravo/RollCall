from datetime import datetime, timezone

from utils.db_schema_crud import (
    create_waiver_approval,
    get_attendance_by_cadet,
    get_event_by_id,
    get_waiver_by_attendance_record,
    update_waiver,
    validate_waiver,
)


def get_all_waivers_for_cadet(cadet_id: str) -> list[dict]:
    """Return all waivers for a cadet, enriched with event name and date."""
    records = get_attendance_by_cadet(cadet_id)
    waivers = []
    for record in records:
        waiver = get_waiver_by_attendance_record(record["_id"])
        if waiver:
            event_id = record.get("event_id")
            event = get_event_by_id(event_id) if event_id else None
            waiver["_event_name"] = event.get("event_name") if event else "Unknown event"
            start_date = event.get("start_date") if event else None
            waiver["_event_date"] = (
                start_date.strftime("%Y-%m-%d") if start_date else "Unknown date"
            )
            waivers.append(waiver)
    return waivers


def get_absent_records_without_waiver(cadet_id: str) -> list[dict]:
    """Return absent attendance records that are eligible for a new waiver submission.

    Includes records with no waiver, and records whose only waiver was auto-denied
    (allowing resubmission).
    """
    records = get_attendance_by_cadet(cadet_id)
    absent = [r for r in records if r.get("status") == "absent"]

    eligible = []
    for record in absent:
        existing = get_waiver_by_attendance_record(record["_id"])
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
