from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from utils.auth import get_current_user, require_role
from utils.datetime_utils import ensure_utc
from utils.db_schema_crud import (
    get_all_cadets,
    get_attendance_by_event,
    get_cadet_by_user_id,
    get_events_by_type,
    get_user_by_email,
    get_user_by_id,
)
from services.events import closest_event_index
from utils.flight_commander_view import build_checkin_view, get_active_events


def _cadet_display_name(cadet: dict[str, Any]) -> str:
    first = str(cadet.get("first_name", "")).strip()
    last = str(cadet.get("last_name", "")).strip()
    full = f"{first} {last}".strip()
    return full or "Unknown cadet"


require_role("flight_commander")
st.title("Live Check-In View")
st.caption(
    "Real-time view of who has checked in for the active event and who is still missing."
)

current_user = get_current_user()
assert current_user is not None

email = str(current_user.get("email", "") or "").strip()
if not email:
    st.error("Could not determine the current user's email.")
    st.stop()

user = get_user_by_email(email)
if user is None:
    st.error("Could not find the current user in the database.")
    st.stop()
assert user is not None

cadet = get_cadet_by_user_id(user["_id"])
if cadet is None:
    st.error("Flight commander profile not found.")
    st.stop()
assert cadet is not None

flight_id = cadet.get("flight_id")
if flight_id is None:
    st.info("You are not assigned to a flight.")
    st.stop()


@st.fragment(run_every="10s")
def live_checkin_fragment() -> None:
    now = datetime.now(timezone.utc)

    all_cadets = get_all_cadets()
    flight_cadets = [c for c in all_cadets if c.get("flight_id") == flight_id]

    if not flight_cadets:
        st.info("No cadets found for your flight.")
        return

    # Enrich cadet docs with names from the users collection when missing.
    enriched_flight_cadets: list[dict[str, Any]] = []
    for cadet_doc in flight_cadets:
        first = str(cadet_doc.get("first_name", "") or "").strip()
        last = str(cadet_doc.get("last_name", "") or "").strip()

        if not first and not last:
            user_id = cadet_doc.get("user_id")
            if user_id is not None:
                user_doc = get_user_by_id(user_id)
                if user_doc is not None:
                    cadet_doc = dict(cadet_doc)
                    cadet_doc["first_name"] = user_doc.get("first_name", "")
                    cadet_doc["last_name"] = user_doc.get("last_name", "")

        enriched_flight_cadets.append(cadet_doc)

    flight_cadets = enriched_flight_cadets

    events = get_events_by_type("pt") + get_events_by_type("lab")
    active_events: list[dict[str, Any]] = get_active_events(events, now)

    if not active_events:
        st.info("No active event right now.")
        return

    # Try to preserve the previously selected event across refreshes.
    previous_event_id = st.session_state.get("fc_selected_event_id")

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

    default_index = closest_event_index(active_events)
    if previous_event_id is not None:
        for idx, ev in enumerate(active_events):
            if ev.get("_id") == previous_event_id:
                default_index = idx
                break

    selected_event = st.selectbox(
        "Select active event to display",
        options=active_events,
        format_func=_event_label,
        index=default_index,
    )

    if isinstance(selected_event, dict):
        st.session_state["fc_selected_event_id"] = selected_event.get("_id")

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


live_checkin_fragment()
