

import streamlit as st

from services.waivers import (
    get_absent_records_without_waiver,
    get_all_waivers_for_cadet,
    resubmit_auto_denied_waiver,
    withdraw_waiver,
)
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    create_waiver,
    get_approvals_by_waiver,
    get_cadet_by_user_id,
    get_event_by_id,
    get_user_by_email,
    get_waiver_by_attendance_record,
    get_waiver_by_id,
    get_attendance_by_cadet,
)
from datetime import datetime


STATUS_BADGE = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
}


def load_waiver_data(cadet_id) -> tuple[list[dict], dict, dict]:
    records = get_attendance_by_cadet(cadet_id)
    waivers_by_record_id = {}
    events_by_id = {}
    for record in records:
        waiver = get_waiver_by_attendance_record(record["_id"])
        if waiver:
            waivers_by_record_id[record["_id"]] = waiver
        event_id = record.get("event_id")
        if event_id and event_id not in events_by_id:
            event = get_event_by_id(event_id)
            if event:
                events_by_id[event_id] = event
    return records, waivers_by_record_id, events_by_id


def show_waivers(
    records: list[dict],
    waivers_by_record_id: dict,
    events_by_id: dict,
):
    st.divider()
    st.subheader("My Waiver Requests")

    waivers = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)
    if not waivers:
        st.info("You don't have any waivers.")
        return

    header = st.columns([3, 3, 2, 2])
    header[0].markdown("**Event**")
    header[1].markdown("**Date**")
    header[2].markdown("**Status**")
    header[3].markdown("**Action**")
    st.divider()

    for waiver in waivers:
        waiver_id = str(waiver["_id"])
        status = (waiver.get("status") or "").lower()

        col = st.columns([3, 3, 2, 2])
        col[0].write(waiver.get("_event_name"))
        col[1].write(waiver.get("_event_date"))
        col[2].write(STATUS_BADGE.get(status.lower(), status))

        approvals = get_approvals_by_waiver(waiver["_id"])
        if approvals:
            approvals.sort(
                key=lambda a: a.get("created_at") or datetime.min, reverse=True
            )
            latest = approvals[0]
            comments = latest.get("comments")
            if comments:
                col[2].caption(comments)

        if status == "pending":
            if st.session_state.confirm_withdraw_id == waiver_id:
                col[3].warning("Are you sure you want to withdraw your waiver?")
                c1, c2 = col[3].columns(2)
                if c1.button("Yes", key=f"yes_{waiver_id}"):
                    success = withdraw_waiver(waiver["_id"])
                    st.session_state.confirm_withdraw_id = None
                    if success:
                        st.session_state.show_success = "Waiver withdrawn."
                    else:
                        st.session_state.show_error = "Failed to withdraw waiver."
                    st.rerun()
                if c2.button("No", key=f"no_{waiver_id}"):
                    st.session_state.confirm_withdraw_id = None
                    st.rerun()
            else:
                if col[3].button("Withdraw", key=f"withdraw_{waiver_id}"):
                    st.session_state.confirm_withdraw_id = waiver_id
                    st.rerun()
        else:
            col[3].write("—")

        st.markdown(f"**Reason:** {waiver['reason']}")
        st.divider()


def dropdown_row(record: dict, events_by_id: dict) -> str:
    event = events_by_id.get(record.get("event_id"))
    if event:
        start_date = event.get("start_date")
        date_str = start_date.strftime("%Y-%m-%d") if start_date else "Unknown date"
        name = event.get("event_name", "Unknown event")
        return f"{date_str} - {name}"
    return str(record["_id"])


def waiver_form(
    user_id: str,
    cadet_id: str,
    records: list[dict],
    waivers_by_record_id: dict,
    events_by_id: dict,
):
    record_id = st.session_state.waiver_record_id
    st.session_state.waiver_record_id = None

    absent_records = get_absent_records_without_waiver(records, waivers_by_record_id)
    if not absent_records:
        st.info("You don't have any absent records to submit a waiver for.")
        return

    record_labels = {dropdown_row(r, events_by_id): r for r in absent_records}

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
            existing = get_waiver_by_attendance_record(selected_record["_id"])

            if (
                existing
                and (existing.get("status") or "").lower() == "denied"
                and bool(existing.get("auto_denied"))
            ):
                became_pending, why = resubmit_auto_denied_waiver(
                    existing, selected_record["_id"], reason
                )
                if not became_pending:
                    st.error(
                        f"Waiver is still invalid and was auto-denied again: {why}"
                    )
                else:
                    st.session_state.show_success = (
                        "Waiver request submitted successfully!"
                    )
                st.rerun()

            else:
                result = create_waiver(
                    attendance_record_id=selected_record["_id"],
                    reason=reason,
                    status="pending",
                    submitted_by_user_id=user_id,
                )

                if result:
                    created = get_waiver_by_id(result.inserted_id)
                    created_status = (created.get("status") if created else "") or ""
                    if created_status.lower() == "denied":
                        st.session_state.show_error = "Waiver was auto-denied. See notes under your waiver status."
                    else:
                        st.session_state.show_success = (
                            "Waiver request submitted successfully!"
                        )
                    st.rerun()
                else:
                    st.session_state.show_error = (
                        "Failed to submit waiver. Please try again."
                    )
                    st.rerun()

    if cancel:
        # should be
        # st.switch_page("pages/8_Cadet_Attendance.py")
        st.switch_page("pages/8_Cadet_Attendance.py")


require_role("cadet")
st.title("Submit Waiver Request")

if "waiver_record_id" not in st.session_state:
    st.session_state.waiver_record_id = None
if "success_time" not in st.session_state:
    st.session_state.success_time = None
if "confirm_withdraw_id" not in st.session_state:
    st.session_state.confirm_withdraw_id = None
if "show_success" not in st.session_state:
    st.session_state.show_success = None
if "show_error" not in st.session_state:
    st.session_state.show_error = None

if st.session_state.show_success:
    st.success(st.session_state.show_success)
    st.session_state.show_success = None
if st.session_state.show_error:
    st.error(st.session_state.show_error)
    st.session_state.show_error = None

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

records, waivers_by_record_id, events_by_id = load_waiver_data(cadet["_id"])

waiver_form(
    str(user["_id"]), str(cadet["_id"]), records, waivers_by_record_id, events_by_id
)
show_waivers(records, waivers_by_record_id, events_by_id)
