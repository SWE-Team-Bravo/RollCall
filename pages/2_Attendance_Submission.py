from __future__ import annotations

import streamlit as st

from services.attendance import is_already_checked_in
from services.cadet_attendance import get_cadet_flight_label, load_cadet_flights
from services.event_codes import validate_code
from utils.auth import get_current_user, require_auth
from utils.auth_logic import user_has_any_role
from utils.db_schema_crud import (
    create_attendance_record,
    get_attendance_by_cadet,
    get_cadet_by_user_id,
    get_event_by_id,
    get_user_by_email,
)


require_auth()
st.title("Attendance Submission")

current_user = get_current_user()
assert current_user is not None

user = get_user_by_email(str(current_user.get("email", "") or "").strip())
if not user:
    st.error("Could not find your account.")
    st.stop()
assert user is not None

role = get_current_user()
cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    if user_has_any_role(current_user, ["admin"]):
        st.info(
            "Admin accounts do not have a cadet profile. Attendance submission is for cadets only."
        )
    else:
        st.error(
            "No cadet profile is linked to your account. "
            "If you are a cadet, contact your cadre to have a profile created."
        )
    st.stop()
assert cadet is not None

cadet_id = cadet["_id"]

first = str(current_user.get("first_name", "") or "").strip()
last = str(current_user.get("last_name", "") or "").strip()
rank = str(cadet.get("rank", "") or "").strip()
flights = load_cadet_flights(cadet)
flight_label = get_cadet_flight_label(cadet, flights)
name_parts = [p for p in [rank, first, last] if p]
st.caption(f"Checking in as **{' '.join(name_parts)}** · Flight: {flight_label}")
st.divider()

st.subheader("Enter your 6-digit event code")

code = st.text_input(
    "Event code",
    max_chars=6,
    placeholder="000000",
    label_visibility="collapsed",
)

code_clean = code.strip()

event_code = None
already_checked_in = False

if len(code_clean) == 6:
    event_code = validate_code(code_clean)
    if event_code is None:
        st.error("Invalid or expired code.")
    else:
        event = get_event_by_id(event_code["event_id"])
        if event:
            event_name = str(event.get("event_name", "") or "Event")
            event_type = (event.get("event_type") or "").upper()
            start = event.get("start_date")
            if hasattr(start, "strftime"):
                date_str = start.strftime("%B %d, %Y")
            elif start:
                date_str = str(start)[:10]
            else:
                date_str = ""

            existing = get_attendance_by_cadet(cadet_id)
            already_checked_in = is_already_checked_in(
                str(event_code["event_id"]), str(cadet_id), existing
            )

            if already_checked_in:
                st.success(
                    f"You are already checked in for **{event_name}**"
                    + (f" ({event_type} · {date_str})" if date_str else "")
                    + "."
                )
            else:
                label = event_name
                if event_type:
                    label += f" · {event_type}"
                if date_str:
                    label += f" · {date_str}"
                st.info(label)

button_disabled = event_code is None or already_checked_in

if (
    st.button("Report In", type="primary", disabled=button_disabled)
    and event_code is not None
):
    existing = get_attendance_by_cadet(cadet_id)
    if is_already_checked_in(str(event_code["event_id"]), str(cadet_id), existing):
        st.info("You are already checked in for this event.")
    else:
        result = create_attendance_record(
            event_id=event_code["event_id"],
            cadet_id=cadet_id,
            status="present",
            recorded_by_user_id=user["_id"],
        )
        if result is None:
            st.error("Database unavailable. Could not record attendance.")
        else:
            event = get_event_by_id(event_code["event_id"])
            event_name = (
                str(event.get("event_name", "") or "the event")
                if event
                else "the event"
            )
            st.success(f"Checked in for **{event_name}**!")
            st.balloons()
