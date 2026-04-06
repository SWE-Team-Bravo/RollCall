from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st
from bson import ObjectId

from utils.auth import get_current_user, require_auth
from utils.db_schema_crud import get_cadet_by_user_id, get_user_by_email
from utils.audit_log import log_checkin_attempt
from utils.checkin_codes import issue_checkin_code, validate_checkin_code
from services.attendance import generate_attendance_password

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

CODE_TTL_MINUTES = 15


def _get_current_cadet_id() -> ObjectId | None:
    current_user = get_current_user()
    if not current_user:
        return None

    email = str(current_user.get("email", "") or "").strip()
    if not email:
        return None

    user_doc = get_user_by_email(email)
    if not user_doc:
        return None
    cadet_doc = get_cadet_by_user_id(user_doc["_id"])
    if not cadet_doc:
        return None

    cadet_id = cadet_doc.get("_id")
    return cadet_id if isinstance(cadet_id, ObjectId) else None


cadet_id = _get_current_cadet_id()

# Generate password once per session
if "password" not in st.session_state:
    st.session_state.password = generate_attendance_password()
    st.session_state.password_created_at = datetime.now(timezone.utc)
    st.session_state.password_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=CODE_TTL_MINUTES
    )
    issue_checkin_code(
        code=st.session_state.password,
        ttl_minutes=CODE_TTL_MINUTES,
        kind="attendance_submission",
        now=st.session_state.password_created_at,
    )
    st.session_state.correctPassword = False
correctPassword = st.session_state.correctPassword
expires_at = st.session_state.get("password_expires_at")

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

if st.button("Report In"):
    now = datetime.now(timezone.utc)

    if correctPassword:
        outcome = "duplicate"
    else:
        db_outcome = validate_checkin_code(
            code=answer,
            kind="attendance_submission",
            now=now,
        )

        if db_outcome in {"success", "expired_code", "invalid_code"}:
            outcome = db_outcome
        else:
            outcome = "invalid_code"

        if outcome == "invalid_code" and isinstance(expires_at, datetime):
            if now > expires_at:
                outcome = "expired_code"

    if cadet_id is not None:
        log_checkin_attempt(
            cadet_id=cadet_id,
            outcome=outcome,
            attempted_code=answer,
            source="attendance_submission",
            now=now,
            metadata={"ttl_minutes": CODE_TTL_MINUTES},
        )

    if outcome == "success":
        st.success("correct password")
        st.balloons()
        st.session_state.correctPassword = True
        attendanceStatus.markdown("Attendance Status: Reported")
    elif outcome == "duplicate":
        st.info("Already reported in this session.")
    elif outcome == "expired_code":
        st.error("Code expired. Please refresh to get a new code.")
    else:
        st.error("wrong password")
