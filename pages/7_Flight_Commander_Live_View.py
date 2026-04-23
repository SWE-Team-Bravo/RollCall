from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from services.attendance_modifications import apply_bulk_attendance_changes
from services.commander_attendance import build_commander_roster, hydrate_cadet_names
from utils.auth import get_current_user, require_role
from utils.st_helpers import require
from utils.attendance_status import NO_RECORD_STATUS_LABEL, get_attendance_status_label
from utils.datetime_utils import ensure_utc
from utils.db_schema_crud import (
    get_all_cadets,
    get_attendance_by_event,
    get_cadet_by_user_id,
    get_events_by_type,
    get_user_by_email,
    get_users_by_ids,
)
from services.events import closest_event_index
from utils.flight_commander_view import build_checkin_view, get_active_events


def _cadet_display_name(cadet: dict[str, Any]) -> str:
    name = str(cadet.get("name", "") or "").strip()
    if name:
        return name

    first = str(cadet.get("first_name", "")).strip()
    last = str(cadet.get("last_name", "")).strip()
    full = f"{first} {last}".strip()
    return full or "Unknown cadet"


def _event_label(event: dict[str, Any]) -> str:
    name = str(event.get("event_name", "Event")).strip() or "Event"
    start = event.get("start_date")
    end = event.get("end_date")
    if isinstance(start, datetime) and isinstance(end, datetime):
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        return (
            f"{name} "
            f"({start_utc.strftime('%Y-%m-%d %I:%M %p')} - "
            f"{end_utc.strftime('%I:%M %p')})"
        )
    return name


def _set_feedback(kind: str, message: str) -> None:
    st.session_state["_fc_attendance_feedback"] = {
        "kind": kind,
        "message": message,
    }


def _show_feedback() -> None:
    feedback = st.session_state.pop("_fc_attendance_feedback", None)
    if not feedback:
        return

    kind = str(feedback.get("kind", "info") or "info")
    message = str(feedback.get("message", "") or "").strip()
    if not message:
        return

    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def _load_flight_cadets(flight_id: Any) -> list[dict[str, Any]]:
    flight_cadets = [
        cadet_doc
        for cadet_doc in get_all_cadets()
        if cadet_doc.get("flight_id") == flight_id
    ]
    if not flight_cadets:
        return []

    user_ids = [
        cadet_doc["user_id"]
        for cadet_doc in flight_cadets
        if cadet_doc.get("user_id") is not None
    ]
    user_by_id = {user_doc["_id"]: user_doc for user_doc in get_users_by_ids(user_ids)}
    return hydrate_cadet_names(flight_cadets, user_by_id)


require_role("flight_commander")
st.title("Live Check-In View")
st.caption(
    "Real-time view of who has checked in for the active event and who is still missing."
)

_show_feedback()

current_user = get_current_user()
assert current_user is not None

email = str(current_user.get("email", "") or "").strip()
if not email:
    st.error("Could not determine the current user's email.")
    st.stop()

user = require(
    get_user_by_email(email), "Could not find the current user in the database."
)

cadet = get_cadet_by_user_id(user["_id"])
if cadet is None:
    st.error("Flight commander profile not found.")
    st.stop()
assert cadet is not None

flight_id = cadet.get("flight_id")
if flight_id is None:
    st.info("You are not assigned to a flight.")
    st.stop()

flight_cadets = _load_flight_cadets(flight_id)
if not flight_cadets:
    st.info("No cadets found for your flight.")
    st.stop()

events = get_events_by_type("pt") + get_events_by_type("lab")
active_events = get_active_events(events, datetime.now(timezone.utc))
if not active_events:
    st.info("No active event right now.")
    st.stop()

previous_event_id = st.session_state.get("fc_selected_event_id")
default_index = closest_event_index(active_events)
if previous_event_id is not None:
    for idx, event_doc in enumerate(active_events):
        if event_doc.get("_id") == previous_event_id:
            default_index = idx
            break

selected_event = st.selectbox(
    "Select active event to display",
    options=active_events,
    format_func=_event_label,
    index=default_index,
)
st.session_state["fc_selected_event_id"] = selected_event.get("_id")


def _save_status(entry: dict[str, Any], status: str) -> None:
    if not get_active_events([selected_event], datetime.now(timezone.utc)):
        _set_feedback(
            "error",
            "The selected event is no longer active. Refresh and choose another event.",
        )
        st.rerun()

    result = apply_bulk_attendance_changes(
        event_id=selected_event["_id"],
        roster=[entry],
        new_statuses={str(entry["cadet"]["_id"]): status},
        recorded_by_user_id=user["_id"],
        recorded_by_roles=list(user.get("roles", [])),
    )

    cadet_name = _cadet_display_name(entry["cadet"])
    status_label = get_attendance_status_label(status, default=status.title())
    if result["changed_count"] == 0:
        _set_feedback("info", f"{cadet_name} is already marked {status_label}.")
    else:
        _set_feedback("success", f"Marked {cadet_name} {status_label}.")
    st.rerun()


@st.fragment(run_every="10s")
def live_checkin_fragment(selected_event: dict[str, Any]) -> None:
    attendance_records = get_attendance_by_event(selected_event["_id"])

    view = build_checkin_view(
        flight_cadets=flight_cadets,
        attendance_records=attendance_records,
        event=selected_event,
    )

    if view is None:
        st.info("No active event right now.")
        return

    event_name = str(view["event"].get("event_name", "Active Event"))
    start = view["event"].get("start_date")
    end = view["event"].get("end_date")

    st.subheader(event_name)
    if isinstance(start, datetime) and isinstance(end, datetime):
        start = ensure_utc(start)
        end = ensure_utc(end)
        st.caption(
            f"{start.strftime('%Y-%m-%d %I:%M %p')} - "
            f"{end.strftime('%I:%M %p')} • Refreshes every 10 seconds"
        )
    else:
        st.caption("Refreshes every 10 seconds")

    checked_in = view["checked_in"]
    missing = view["missing"]

    top = st.columns(3)
    top[0].metric("Checked In", len(checked_in))
    top[1].metric("Missing", len(missing))
    top[2].metric("Total Flight Cadets", len(flight_cadets))

    left, right = st.columns(2)

    with left:
        st.success(f"Checked In ({len(checked_in)})")
        if checked_in:
            for cadet_doc in checked_in:
                st.write(f"✅ {_cadet_display_name(cadet_doc)}")
        else:
            st.info("No one has checked in yet.")

    with right:
        st.error(f"Still Missing ({len(missing)})")
        if missing:
            for cadet_doc in missing:
                st.write(f"⚠️ {_cadet_display_name(cadet_doc)}")
        else:
            st.info("Everyone is checked in.")

    st.divider()


live_checkin_fragment(selected_event)

attendance_records = get_attendance_by_event(selected_event["_id"])
roster = build_commander_roster(flight_cadets, attendance_records)

st.subheader("Manual Attendance")
st.caption(
    "Mark cadets in your flight present or absent for the selected active event. "
    "These updates override self-check-ins."
)

with st.container(border=True):
    for entry in roster:
        cadet_doc = entry["cadet"]
        cadet_name = _cadet_display_name(cadet_doc)
        current_status = entry.get("current_status")
        current_status_label = get_attendance_status_label(
            current_status,
            default=NO_RECORD_STATUS_LABEL,
        )
        cadet_key = str(cadet_doc.get("_id"))

        info_col, present_col, absent_col = st.columns([6, 1, 1])
        info_col.write(cadet_name)
        info_col.caption(f"Current status: {current_status_label}")

        if present_col.button(
            "Present",
            key=f"fc_present_{selected_event['_id']}_{cadet_key}",
            width="stretch",
            disabled=current_status == "present",
        ):
            _save_status(entry, "present")

        if absent_col.button(
            "Absent",
            key=f"fc_absent_{selected_event['_id']}_{cadet_key}",
            width="stretch",
            disabled=current_status == "absent",
        ):
            _save_status(entry, "absent")
