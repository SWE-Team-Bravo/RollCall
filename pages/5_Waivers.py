import streamlit as st
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    get_cadet_by_user_id,
    get_user_by_email,
    get_event_by_id,
    get_attendance_by_cadet,
    get_waiver_by_attendance_record,
    create_waiver,
)
import time


STATUS_BADGE = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
}


def get_all_waivers_for_cadet(cadet_id: str) -> list[dict]:
    records = get_attendance_by_cadet(cadet_id)
    waivers = []
    for record in records:
        waiver = get_waiver_by_attendance_record(record["_id"])
        if waiver:
            event_id = record.get("event_id")
            event = get_event_by_id(event_id) if event_id else None
            waiver["_event_name"] = (
                event.get("event_name") if event else "Unknown event"
            )
            start_date = event.get("start_date") if event else None
            waiver["_event_date"] = (
                start_date.strftime("%Y-%m-%d") if start_date else "Unknown date"
            )
            waivers.append(waiver)
    return waivers


def show_waivers(cadet_id: str):
    st.divider()
    st.subheader("My Waiver Requests")

    waivers = get_all_waivers_for_cadet(cadet_id)
    if not waivers:
        st.info("You don't have any waivers.")
        return

    header = st.columns([3, 3, 2])
    header[0].markdown("**Event**")
    header[1].markdown("**Date**")
    header[2].markdown("**Status**")
    st.divider()

    for waiver in waivers:
        col = st.columns([3, 3, 2])
        col[0].write(waiver.get("_event_name"))
        col[1].write(waiver.get("_event_date"))
        status = waiver.get("status") or ""
        col[2].write(STATUS_BADGE.get(status.lower(), status))
        st.markdown(f"**Reason:** {waiver['reason']}")
        st.divider()


def dropdown_row(record: dict) -> str:
    event_id = record.get("event_id")
    event = get_event_by_id(event_id) if event_id else None
    if event:
        start_date = event.get("start_date")
        date_str = start_date.strftime("%Y-%m-%d") if start_date else "Unknown date"
        name = event.get("event_name", "Unknown event")
        return f"{date_str} - {name}"
    return str(record["_id"])


def get_absent_records(cadet_id: str) -> list[dict]:
    records = get_attendance_by_cadet(cadet_id)
    absent = [r for r in records if r.get("status") == "absent"]

    no_waiver = []
    for record in absent:
        existing = get_waiver_by_attendance_record(record["_id"])
        if not existing:
            no_waiver.append(record)
    return no_waiver


def waiver_form(user_id: str, cadet_id: str):
    record_id = st.session_state.waiver_record_id
    st.session_state.waiver_record_id = None

    absent_records = get_absent_records(cadet_id)
    if not absent_records:
        st.info("You don't have any absent records to submit a waiver for.")
        return

    record_labels = {dropdown_row(r): r for r in absent_records}

    default_index = 0
    if record_id:
        for i, record in enumerate(absent_records):
            if str(record["_id"]) == record_id:
                default_index = i
                break

    with st.form("waiver_form", clear_on_submit=True):
        label = st.selectbox(
            "Select Absent Event",
            options=list(record_labels.keys()),
            index=default_index,
        )
        reason = st.text_area("Reason for Waiver Request")

        col1, col2, spacer = st.columns([2, 2, 8])
        with col1:
            submit = st.form_submit_button("Submit")
        with col2:
            cancel = st.form_submit_button("Cancel", type="secondary")
    if submit:
        if not reason.strip():
            st.error("Please provide a reason for your waiver request.")
        else:
            selected_record = record_labels[label]
            result = create_waiver(
                attendance_record_id=selected_record["_id"],
                reason=reason,
                status="pending",
                submitted_by_user_id=user_id,
            )
            if result:
                st.session_state.success_time = time.time()
                st.rerun()
            else:
                st.error("Failed to submit waiver. Please try again.")
    if cancel:
        # i'm confused from where we're supposed to access waiver submission form, this can be changed later
        st.switch_page("pages/2_Attendance_Submission.py")


require_role("cadet")
st.title("Submit Waiver Request")

if "waiver_record_id" not in st.session_state:
    st.session_state.waiver_record_id = None
if "success_time" not in st.session_state:
    st.session_state.success_time = None

success_placeholder = st.empty()
if st.session_state.success_time:
    if time.time() - st.session_state.success_time < 3:
        success_placeholder.success("Waiver request submitted successfully!")
        st.rerun()
    else:
        success_placeholder.empty()
        st.session_state.success_time = None
        st.rerun()

current_user = get_current_user()
assert current_user is not None

email = current_user["email"]
if not email:
    st.error("Could not find an account with this email.")
    st.stop()

user = get_user_by_email(email)
if not user:
    st.error("Could not find an account with this email.")
    st.stop()
assert user is not None

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    st.error("You must be a cadet to submit a waiver request.")
    st.stop()
assert cadet is not None

waiver_form(str(user["_id"]), str(cadet["_id"]))
show_waivers(str(cadet["_id"]))
