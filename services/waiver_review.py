from __future__ import annotations
from datetime import datetime
from bson import ObjectId
import pandas as pd

from utils.db_schema_crud import (
    create_waiver_approval,
    get_all_flights,
    get_all_waivers,
    get_attendance_record_by_id,
    get_cadet_by_id,
    get_event_by_id,
    get_flight_by_id,
    get_user_by_id,
    update_waiver,
)

from utils.names import format_full_name
from utils.waiver_email import send_waiver_decision_email


def _fmt_date(dt: object) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return "Unknown date"


def get_flight_options() -> list[str]:
    flights = get_all_flights()
    return ["All flights"] + [f.get("name", "Unnamed flight") for f in flights]


def get_waivers(
    status_filter: str, viewer_roles: list[str] | None = None
) -> list[dict]:
    waivers = get_all_waivers()
    if status_filter != "all":
        waivers = [
            w for w in waivers if (w.get("status") or "").lower() == status_filter
        ]

    roles = set(viewer_roles or [])
    if not (roles & {"admin", "cadre"}):
        waivers = [w for w in waivers if not w.get("cadre_only", False)]

    waivers.sort(key=lambda w: w.get("created_at") or datetime.min, reverse=True)
    return waivers


def get_waiver_context(waiver: dict) -> dict | None:
    """
    For a single waiver, fetch and return all related data.
    Returns None if any required data is missing.
    """
    attendance_record_id = waiver.get("attendance_record_id")
    if attendance_record_id is None:
        return None

    record = get_attendance_record_by_id(attendance_record_id)
    if record is None:
        return None

    event = None
    event_id = record.get("event_id")
    if event_id is not None:
        event = get_event_by_id(event_id)

    cadet = None
    cadet_id = record.get("cadet_id")
    if cadet_id is not None:
        cadet = get_cadet_by_id(cadet_id)

    user = None
    if cadet is not None:
        user_id = cadet.get("user_id")
        if user_id is not None:
            user = get_user_by_id(user_id)

    flight_name = "Unassigned"
    if cadet is not None:
        cadet_flight_id = cadet.get("flight_id")
        if cadet_flight_id is not None:
            flight = get_flight_by_id(cadet_flight_id)
            if flight:
                flight_name = flight.get("name", "Unassigned")

    cadet_name = format_full_name(user, "Unknown cadet")

    return {
        "cadet_name": cadet_name,
        "cadet_email": user.get("email") if user else "",
        "flight_name": flight_name,
        "event_name": event.get("event_name") if event else "Unknown event",
        "event_date": _fmt_date(event.get("start_date") if event else None),
        "event_type": (event.get("event_type") if event else "") or "unknown",
        "waiver_type": waiver.get("waiver_type") or "non-medical",
        "attachments": waiver.get("attachments") or [],
        "cadre_only": bool(waiver.get("cadre_only", False)),
    }


def submit_decision(
    waiver_id: str | ObjectId,
    approver_id: str | ObjectId,
    decision: str,
    comments: str,
    cadet_email: str,
    event_name: str,
    event_date: str,
) -> tuple[bool, str]:
    new_status = "approved" if decision == "Approve" else "denied"
    upd = update_waiver(waiver_id, {"status": new_status})
    if upd is None:
        return False, "Failed to update waiver status."

    appr = create_waiver_approval(
        waiver_id=waiver_id,
        approver_id=approver_id,
        decision=new_status,
        comments=comments or "Approved.",
    )
    if appr is None:
        return False, "Failed to create waiver approval record."

    if cadet_email:
        send_waiver_decision_email(
            waiver_id=str(waiver_id),
            to_email=cadet_email,
            event_name=event_name or "Unknown event",
            event_date=event_date,
            status=new_status,
            comments=comments or "Approved.",
        )

    return True, ""


def get_waiver_export_df(rows: list[dict]) -> pd.DataFrame | str:
    if not rows:
        return "No waivers found."
    return pd.DataFrame(
        [
            {
                "Cadet": r["cadet_name"],
                "Email": r["cadet_email"],
                "Flight": r["flight_name"],
                "Event": r["event_name"],
                "Date": r["event_date"],
                "Status": r["waiver_status"],
                "Type": r.get("waiver_type", "non-medical"),
                "Reason": r["reason"],
            }
            for r in rows
        ]
    )
