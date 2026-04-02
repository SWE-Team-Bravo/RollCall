import streamlit as st
import secrets
from datetime import datetime, timedelta, timezone
from utils.db import get_collection  # <-- use shared db helper
from utils.auth import get_current_user, require_auth
from utils.db_schema_crud import (
    create_attendance_record,
    get_attendance_by_event,
    get_cadet_by_user_id,
    get_events_by_type,
    get_user_by_email,
)
from utils.flight_commander_view import get_active_events
from services.attendance import is_already_checked_in


# =====Database stuff=====#
def getPassword():
    pswdData = get_collection("Password")  # uses MONGODB_URI + MONGODB_DB from config
    assert pswdData is not None

    # Checks that password collection has data
    count = pswdData.count_documents({})
    if count > 0:
        # Grabs the most recent password
        mostrecent = pswdData.find_one(sort=[("$natural", -1)])
        assert mostrecent is not None

        # Check if xx time has passed
        if datetime.now() - mostrecent["timestamp"] >= timedelta(
            seconds=10
        ):  # Use timedelta(minutes=30) for
            # Creates and adds new password if set time has passed
            pswd = {
                "password": f"{secrets.randbelow(1000000):06}",
                "timestamp": datetime.now(),
            }
            pswdData.insert_one(pswd)
    else:
        # Adds initial data to the database
        pswd = {"password": 123456, "timestamp": datetime.now()}
        pswdData.insert_one(pswd)

    result = pswdData.find_one(sort=[("$natural", -1)])
    assert result is not None
    return str(result["password"])


# =====Streamlit stuff=====#

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
active_events = get_active_events(events, now)

if not active_events:
    st.info("No active event right now.")
    st.stop()

active_event = active_events[0]
event_id = active_event["_id"]

# Generate password once per session
if "password" not in st.session_state:
    st.session_state.correctPassword = False
correctPassword = st.session_state.correctPassword

# Writes the password for testing purposes
st.info("testing password: " + getPassword())

# Current day of the week
weekDay = datetime.now().strftime("%A")
# st.info(weekDay)

# Default message for attendance status
# Default message for attendance status
attendanceStatus = st.empty()
if correctPassword:
    attendanceStatus.markdown("Attendance Status: Reported")
else:
    attendanceStatus.markdown("Attendance Status: Needs Reported")

# Password submission and checking
answer = st.text_input("Password", type="password")

if st.button("Report In") and not correctPassword:
    if answer == getPassword():
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
