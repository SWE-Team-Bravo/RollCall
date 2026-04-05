import streamlit as st
from datetime import datetime, timezone

from utils.auth import get_current_user, require_auth
from utils.db_schema_crud import (
    create_attendance_record,
    get_attendance_by_event,
    get_cadet_by_user_id,
    get_events_by_type,
    get_user_by_email,
)
from services.attendance import (
    generate_attendance_password,
    is_already_checked_in,
    is_within_checkin_window,
)

require_auth()
st.title("Attendance Submission Page")

current_user = get_current_user()
assert current_user is not None

email = current_user["email"]
user = get_user_by_email(email)
if not user:
    st.error("Could not find your account.")
    st.stop()
assert user is not None

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    st.error("No cadet profile found for your account.")
    st.stop()
assert cadet is not None

now = datetime.now(timezone.utc)
events = get_events_by_type("pt") + get_events_by_type("lab")
active_events = [e for e in events if is_within_checkin_window(e, now)]

if not active_events:
    st.info("No active event right now.")
    st.stop()

active_event = active_events[0]
event_id = active_event["_id"]

# Generate password once per session
if "password" not in st.session_state:
    st.session_state.password = generate_attendance_password()
    st.session_state.correctPassword = False
password = st.session_state.password
correctPassword = st.session_state.correctPassword

# Writes the password for testing purposes
st.info("testing password: " + password)

# Current day of the week
weekDay = datetime.now().strftime("%A")
# st.info(weekDay)

# Default message for attendance status
attendanceStatus = st.empty()
if correctPassword:
    attendanceStatus.markdown("Attendance Status: Reported")
else:
    attendanceStatus.markdown("Attendance Status: Needs Reported")

# Password submission and checking
answer = st.text_input("Password", type="password")

if st.button("Report In") and not correctPassword:
    if answer == password:
        existing_records = get_attendance_by_event(event_id)
        if is_already_checked_in(str(event_id), str(cadet["_id"]), existing_records):
            st.warning("You have already checked in for this event.")
        else:
            create_attendance_record(
                event_id=event_id,
                cadet_id=cadet["_id"],
                status="present",
                recorded_by_user_id=user["_id"],
            )
            st.success("correct password")
            st.balloons()
            st.session_state.correctPassword = True
            attendanceStatus.markdown("Attendance Status: Reported")
    else:
        st.error("wrong password")
