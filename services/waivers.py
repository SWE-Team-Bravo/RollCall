from datetime import datetime, timezone

from utils.db_schema_crud import (
    create_waiver_approval,
    get_sickness_waivers_by_user,
    get_waiver_by_id,
    update_waiver,
    validate_waiver,
)

COMMON_REASONS = [
    "Military Orders",
    "Sick with documentation",
    "Sick without documentation",
    "Sport team",
    "Crosstown (PASSED PFA)",
    "Crosstown (FAILED PFA)",
    "Missed alarm",
    "Out of regs",
    "Late",
    "Vacation, wedding, out of town, etc.",
    "Lack of sleep",
    "Flat tire, icy roads, etc.",
    "Injury",
    "School obligation (change of class time, scholarship requirement, etc.)",
    "Work",
    "Personal/family emergency",
    "FTX excuse",
    "Other (describe below)",
]


def get_common_reasons() -> list[str]:
    return COMMON_REASONS


def is_first_sickness_waiver(user_id) -> bool:
    """Return True if this cadet has no prior approved/pending sickness waivers."""
    return len(get_sickness_waivers_by_user(user_id)) == 0


def apply_sickness_auto_approval(waiver_id, user_id) -> bool:
    """Auto-approve a sickness waiver if it is the cadet's first. Returns True if approved."""
    waiver = get_waiver_by_id(waiver_id)
    if not waiver:
        return False
    if waiver.get("waiver_type") != "sickness":
        return False
    if (waiver.get("status") or "").lower() != "pending":
        return False

    existing = get_sickness_waivers_by_user(user_id)
    other_sickness = [w for w in existing if str(w["_id"]) != str(waiver_id)]
    if other_sickness:
        return False

    update_waiver(waiver_id, {"status": "approved"})
    create_waiver_approval(
        waiver_id=waiver_id,
        approver_id=None,
        decision="approved",
        comments="Auto-approved: first sickness waiver.",
    )
    return True


def resolve_cadre_only(
    waiver_type: str, has_attachment: bool, user_cadre_only: bool
) -> bool:
    """Medical waivers and waivers with attachments always go to cadre only."""
    if waiver_type == "medical" or has_attachment:
        return True
    return user_cadre_only


WAIVER_STATUS_BADGE: dict[str, str] = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
    "withdrawn": "⚪ Withdrawn",
}


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
        waiver["_event_name"] = event.get("event_name") if event else "Unknown event"
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
            if (status == "denied" and auto_denied) or status == "withdrawn":
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
    result = update_waiver(waiver_id, {"status": "withdrawn"})
    return bool(result and result.modified_count > 0)
