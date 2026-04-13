import streamlit as st
import pandas as pd

from bson import ObjectId

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
from datetime import date, datetime, timedelta
from utils.auth_logic import user_has_any_role
from scripts.demo_admin import get_temp_cadet

STATUS_BADGE = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
    "withdrawn": "⚪ Withdrawn",
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

    st.subheader("Filters")
    filter_col1, filter_col2, filter_col3 = st.columns([2, 3, 4])

    status_options = [
        ("All", None),
        ("Pending", "pending"),
        ("Approved", "approved"),
        ("Denied", "denied"),
        ("Withdrawn", "withdrawn"),
    ]
    status_labels = [x[0] for x in status_options]

    with filter_col1:
        selected_status_label = st.selectbox(
            "Status",
            options=status_labels,
            index=status_labels.index("Pending"),
        )
    selected_status = dict(status_options).get(selected_status_label)

    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    with filter_col2:
        date_value = st.date_input(
            "Date range",
            value=(default_start, today),
        )

    # Streamlit returns a single date while the user is mid-selecting a range.
    start_date: date = default_start
    end_date: date = today

    if isinstance(date_value, date):
        start_date = date_value
        end_date = today
        st.info("Select an end date to complete the range (using today for now).")
    elif isinstance(date_value, tuple):
        match date_value:
            case (start, end):
                start_date = start
                end_date = end
            case (start,):
                start_date = start
                end_date = today
                st.info(
                    "Select an end date to complete the range (using today for now)."
                )
            case _:
                start_date = default_start
                end_date = today
                st.info(
                    "Select an end date to complete the range (using today for now)."
                )
    elif isinstance(date_value, list):
        match tuple(date_value):
            case (start, end):
                start_date = start
                end_date = end
            case (start,):
                start_date = start
                end_date = today
                st.info(
                    "Select an end date to complete the range (using today for now)."
                )
            case _:
                start_date = default_start
                end_date = today
                st.info(
                    "Select an end date to complete the range (using today for now)."
                )
    else:
        start_date = default_start
        end_date = today
        st.info("Select an end date to complete the range (using today for now).")

    if start_date > end_date:
        # Be forgiving for mid-selection / accidental reversal.
        start_date, end_date = end_date, start_date

    with filter_col3:
        search = st.text_input("Search (event)", value="")

    # Apply filters
    search_norm = search.strip().lower()

    def _in_date_range(event_date_str: str) -> bool:
        s = (event_date_str or "").strip()
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            # Keep unknown/unparseable dates visible.
            return True
        return start_date <= d <= end_date

    filtered_waivers: list[dict] = []
    for w in waivers:
        status_raw = str(w.get("status", "") or "").lower()
        if selected_status is not None and status_raw != selected_status:
            continue

        if not _in_date_range(str(w.get("_event_date", "") or "")):
            continue

        if search_norm:
            ev_name = str(w.get("_event_name", "") or "").lower()
            if search_norm not in ev_name:
                continue

        filtered_waivers.append(w)

    if not filtered_waivers:
        st.info("No waivers match your filters.")
        return

    waiver_by_id: dict[str, dict] = {str(w["_id"]): w for w in filtered_waivers}

    rows: list[dict[str, str]] = []
    for waiver in filtered_waivers:
        status_raw = (waiver.get("status") or "").lower()
        rows.append(
            {
                "Event": str(waiver.get("_event_name", "") or ""),
                "Date": str(waiver.get("_event_date", "") or ""),
                "Status": str(STATUS_BADGE.get(status_raw, status_raw) or ""),
            }
        )

    df = pd.DataFrame(rows, columns=pd.Index(["Event", "Date", "Status"]))
    st.dataframe(df, hide_index=True, width='stretch')

    st.divider()

    if "selected_waiver_id" not in st.session_state:
        st.session_state.selected_waiver_id = next(iter(waiver_by_id.keys()), None)
    elif st.session_state.selected_waiver_id not in waiver_by_id:
        st.session_state.selected_waiver_id = next(iter(waiver_by_id.keys()), None)

    def _waiver_label(waiver_id: str) -> str:
        w = waiver_by_id.get(waiver_id, {})
        ev = str(w.get("_event_name", "") or "").strip() or "Event"
        dt = str(w.get("_event_date", "") or "").strip()
        st_raw = str((w.get("status") or "")).lower()
        badge = STATUS_BADGE.get(st_raw, st_raw)
        left = f"{dt} — {ev}".strip(" —")
        return f"{left} ({badge})".strip()

    selected_id = st.selectbox(
        "Select waiver",
        options=list(waiver_by_id.keys()),
        format_func=_waiver_label,
        key="selected_waiver_id",
    )

    selected = waiver_by_id.get(str(selected_id)) if selected_id else None
    if not selected:
        return

    approvals = get_approvals_by_waiver(selected["_id"])
    latest_comment = None
    if approvals:
        approvals.sort(key=lambda a: a.get("created_at") or datetime.min, reverse=True)
        latest_comment = approvals[0].get("comments")

    reason = str(selected.get("reason", "") or "").strip()
    if reason:
        st.markdown(f"**Reason:** {reason}")
    if latest_comment:
        st.caption(str(latest_comment))

    status = str((selected.get("status") or "")).lower()
    waiver_id = str(selected["_id"])
    if status == "pending":
        if st.session_state.confirm_withdraw_id == waiver_id:
            st.warning("Are you sure you want to withdraw your waiver?")
            c1, c2 = st.columns(2)
            if c1.button("Yes", key=f"yes_{waiver_id}"):
                success = withdraw_waiver(selected["_id"])
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
            if st.button("Withdraw", key=f"withdraw_{waiver_id}"):
                st.session_state.confirm_withdraw_id = waiver_id
                st.rerun()


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

# cadet = get_cadet_by_user_id(user["_id"])
# if not cadet:
#     st.error("You must be a cadet to submit a waiver request.")
#     st.stop()
# assert cadet is not None

role = get_current_user()
cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    if not user_has_any_role(role, ["admin"]):
        st.error("No cadet profile found for your account.")
        st.stop()
    else:
        cadet = get_temp_cadet()
else: 
    assert cadet is not None

records, waivers_by_record_id, events_by_id = load_waiver_data(cadet["_id"])

waiver_form(
    str(user["_id"]), str(cadet["_id"]), records, waivers_by_record_id, events_by_id
)
show_waivers(records, waivers_by_record_id, events_by_id)
