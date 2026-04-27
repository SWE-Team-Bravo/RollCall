from datetime import date, datetime, timezone

from bson import ObjectId

from services.event_config import get_event_config
from utils.audit_log import log_attendance_modification
from utils.date_range import expand_event_dates
from utils.datetime_utils import ensure_utc
from utils.db_schema_crud import (
    create_waiver_approval,
    get_attendance_record_by_event_cadet,
    get_attendance_record_by_id,
    get_cadet_by_user_id,
    get_events_by_date_range,
    get_sickness_waivers_by_user,
    get_waiver_by_id,
    update_waiver,
    upsert_attendance_record,
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


_DEFAULT_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
_DEFAULT_LLAB_DAYS = ["Friday"]
_DISTRIBUTE_AUDIT_SOURCE = "attendance_modification"


def _scheduled_days() -> tuple[list[str], list[str]]:
    config = get_event_config() or {}
    return (
        config.get("pt_days", _DEFAULT_PT_DAYS),
        config.get("llab_days", _DEFAULT_LLAB_DAYS),
    )


def _filter_days_by_event_types(
    pt_days: list[str],
    llab_days: list[str],
    event_types: list[str] | None,
) -> tuple[list[str], list[str]]:
    types = {t.lower() for t in (event_types or ["pt", "lab"])}
    return (pt_days if "pt" in types else [], llab_days if "lab" in types else [])


def compute_standing_waiver_dates(
    start: date,
    end: date,
    event_types: list[str] | None = None,
) -> list[dict]:
    """Return event-eligible dates a standing waiver would cover.

    Uses the configured PT/LLAB days from event_config, optionally narrowed
    by `event_types` (any of "pt", "lab"). Each entry has the same shape as
    `expand_event_dates`: {"date", "type", "day"}.
    """
    pt_days, llab_days = _scheduled_days()
    pt_days, llab_days = _filter_days_by_event_types(pt_days, llab_days, event_types)
    return expand_event_dates(start, end, pt_days, llab_days)


def validate_standing_waiver(
    start: date,
    end: date,
    event_types: list[str] | None = None,
) -> tuple[bool, str]:
    """Return (is_valid, why) for a proposed standing waiver date range."""
    if end < start:
        return False, "End date must be on or after start date."

    today = datetime.now(timezone.utc).date()
    if start.year != today.year or end.year != today.year:
        return False, "Standing waiver dates must be in the current year."

    covered = compute_standing_waiver_dates(start, end, event_types)
    if not covered:
        return False, "Date range does not cover any PT or LLAB days."

    return True, ""


def _waiver_event_type_filter(waiver: dict) -> list[str]:
    types = waiver.get("event_types") or ["pt", "lab"]
    return [str(t).lower() for t in types]


def _set_attendance_excused(
    *,
    record: dict,
    cadet_id: ObjectId,
    event_id: ObjectId,
    actor_user_id: str | ObjectId,
    waiver_id: str | ObjectId,
) -> bool:
    """Flip an absent record to excused. Returns True if changed."""
    current_status = (record.get("status") or "").lower()
    if current_status != "absent":
        return False

    upsert_attendance_record(
        event_id=event_id,
        cadet_id=cadet_id,
        status="excused",
        recorded_by_user_id=actor_user_id,
        recorded_by_roles=["system"],
    )
    log_attendance_modification(
        event_id=event_id,
        cadet_id=cadet_id,
        user_id=actor_user_id,
        outcome="applied",
        old_status="absent",
        new_status="excused",
        source=_DISTRIBUTE_AUDIT_SOURCE,
        metadata={
            "waiver_id": str(waiver_id),
            "reason": "waiver_approved",
        },
    )
    return True


def _set_attendance_absent(
    *,
    record: dict,
    cadet_id: ObjectId,
    event_id: ObjectId,
    actor_user_id: str | ObjectId,
    waiver_id: str | ObjectId,
) -> bool:
    """Revert an excused record back to absent. Returns True if changed."""
    current_status = (record.get("status") or "").lower()
    if current_status != "excused":
        return False

    upsert_attendance_record(
        event_id=event_id,
        cadet_id=cadet_id,
        status="absent",
        recorded_by_user_id=actor_user_id,
        recorded_by_roles=["system"],
    )
    log_attendance_modification(
        event_id=event_id,
        cadet_id=cadet_id,
        user_id=actor_user_id,
        outcome="applied",
        old_status="excused",
        new_status="absent",
        source=_DISTRIBUTE_AUDIT_SOURCE,
        metadata={
            "waiver_id": str(waiver_id),
            "reason": "waiver_denied",
        },
    )
    return True


def distribute_excused_status(
    waiver: dict,
    actor_user_id: str | ObjectId,
) -> int:
    """Apply 'excused' to attendance records covered by an approved waiver.

    Singular waivers update a single record. Standing waivers find every
    PT/LLAB attendance record for the cadet inside [start_date, end_date]
    and mark each absent record as excused. Returns the number of records
    actually updated.
    """
    waiver_id = waiver.get("_id")
    if waiver_id is None:
        return 0

    if waiver.get("is_standing"):
        return _distribute_standing(waiver, actor_user_id)

    record_id = waiver.get("attendance_record_id")
    if record_id is None:
        return 0
    record = get_attendance_record_by_id(record_id)
    if record is None:
        return 0
    changed = _set_attendance_excused(
        record=record,
        cadet_id=ObjectId(record["cadet_id"]),
        event_id=ObjectId(record["event_id"]),
        actor_user_id=actor_user_id,
        waiver_id=waiver_id,
    )
    return 1 if changed else 0


def revert_excused_status(
    waiver: dict,
    actor_user_id: str | ObjectId,
) -> int:
    """Undo `distribute_excused_status` for a waiver: excused -> absent."""
    waiver_id = waiver.get("_id")
    if waiver_id is None:
        return 0

    if waiver.get("is_standing"):
        return _revert_standing(waiver, actor_user_id)

    record_id = waiver.get("attendance_record_id")
    if record_id is None:
        return 0
    record = get_attendance_record_by_id(record_id)
    if record is None:
        return 0
    changed = _set_attendance_absent(
        record=record,
        cadet_id=ObjectId(record["cadet_id"]),
        event_id=ObjectId(record["event_id"]),
        actor_user_id=actor_user_id,
        waiver_id=waiver_id,
    )
    return 1 if changed else 0


def _resolve_standing_target(
    waiver: dict,
) -> tuple[ObjectId, datetime, datetime, list[str]] | None:
    submitter_id = waiver.get("submitted_by_user_id")
    start = waiver.get("start_date")
    end = waiver.get("end_date")
    if (
        submitter_id is None
        or not isinstance(start, datetime)
        or not isinstance(end, datetime)
    ):
        return None
    cadet = get_cadet_by_user_id(submitter_id)
    if cadet is None:
        return None
    return (
        ObjectId(cadet["_id"]),
        ensure_utc(start),
        ensure_utc(end),
        _waiver_event_type_filter(waiver),
    )


def _distribute_standing(waiver: dict, actor_user_id: str | ObjectId) -> int:
    target = _resolve_standing_target(waiver)
    if target is None:
        return 0
    cadet_id, start, end, event_types = target
    waiver_id = waiver["_id"]

    events = get_events_by_date_range(start, end, event_types=event_types)
    updated = 0
    for event in events:
        event_id = ObjectId(event["_id"])
        record = get_attendance_record_by_event_cadet(event_id, cadet_id)
        if record is None:
            continue
        if _set_attendance_excused(
            record=record,
            cadet_id=cadet_id,
            event_id=event_id,
            actor_user_id=actor_user_id,
            waiver_id=waiver_id,
        ):
            updated += 1
    return updated


def _revert_standing(waiver: dict, actor_user_id: str | ObjectId) -> int:
    target = _resolve_standing_target(waiver)
    if target is None:
        return 0
    cadet_id, start, end, event_types = target
    waiver_id = waiver["_id"]

    events = get_events_by_date_range(start, end, event_types=event_types)
    reverted = 0
    for event in events:
        event_id = ObjectId(event["_id"])
        record = get_attendance_record_by_event_cadet(event_id, cadet_id)
        if record is None:
            continue
        if _set_attendance_absent(
            record=record,
            cadet_id=cadet_id,
            event_id=event_id,
            actor_user_id=actor_user_id,
            waiver_id=waiver_id,
        ):
            reverted += 1
    return reverted
