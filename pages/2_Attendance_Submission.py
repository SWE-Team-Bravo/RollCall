from __future__ import annotations

import streamlit as st

from services.attendance import is_already_checked_in
from services.event_codes import validate_code
from utils.auth import get_current_user, require_auth
from utils.db_schema_crud import (
    create_attendance_record,
    get_attendance_by_cadet,
    get_cadet_by_user_id,
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

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    st.error("No cadet profile found for your account.")
    st.stop()
assert cadet is not None

cadet_id = cadet["_id"]

code = st.text_input("Enter event code", max_chars=6, placeholder="000000")

if st.button("Report In", type="primary"):
    if not code.strip():
        st.error("Please enter a code.")
    else:
        event_code = validate_code(code.strip())
        if event_code is None:
            st.error("Invalid or expired code.")
        else:
            event_id = event_code["event_id"]
            existing = get_attendance_by_cadet(cadet_id)
            if is_already_checked_in(str(event_id), str(cadet_id), existing):
                st.info("You are already checked in for this event.")
            else:
                result = create_attendance_record(
                    event_id=event_id,
                    cadet_id=cadet_id,
                    status="present",
                    recorded_by_user_id=user["_id"],
                )
                if result is None:
                    st.error("Database unavailable. Could not record attendance.")
                else:
                    st.success("Checked in!")
                    st.balloons()
