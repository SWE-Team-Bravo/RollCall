from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from scripts.demo_admin import get_temp_cadet
from services.admin_users import confirm_destructive_action

from services.waivers import (
    WAIVER_STATUS_BADGE,
    apply_sickness_auto_approval,
    compute_standing_waiver_dates,
    get_absent_records_without_waiver,
    get_common_reasons,
    resolve_cadre_only,
    resubmit_auto_denied_waiver,
    validate_standing_waiver,
    withdraw_waiver,
)
from utils.auth import get_current_user, require_role
from utils.auth_logic import user_has_any_role
from utils.date_range import parse_streamlit_date_range
from utils.db_schema_crud import (
    create_waiver,
    get_approvals_by_waiver,
    get_attendance_by_cadet,
    get_cadet_by_user_id,
    get_event_by_id,
    get_standing_waivers_by_user,
    get_user_by_email,
    get_waiver_by_attendance_record,
    get_waiver_by_id,
)
from utils.st_helpers import require

STATUS_BADGE = WAIVER_STATUS_BADGE


require_role("cadet")


def load_waiver_data(cadet_id, user_id) -> tuple[list[dict], dict, list[dict], dict]:
    records = get_attendance_by_cadet(cadet_id)
    waivers_by_record_id = {}
    all_waivers: list[dict] = []
    events_by_id = {}

    for record in records:
        active_waiver = get_waiver_by_attendance_record(record["_id"])
        if active_waiver:
            waivers_by_record_id[record["_id"]] = active_waiver

        from utils.db_schema_crud import get_waivers_by_attendance_records

        record_waivers = get_waivers_by_attendance_records([record["_id"]])
        all_waivers.extend(record_waivers)

        event_id = record.get("event_id")
        if event_id and event_id not in events_by_id:
            event = get_event_by_id(event_id)
            if event:
                events_by_id[event_id] = event

    all_waivers.extend(get_standing_waivers_by_user(user_id))

    return records, waivers_by_record_id, all_waivers, events_by_id


def show_waivers(
    records: list[dict],
    all_waivers: list[dict],
    events_by_id: dict,
):
    st.divider()
    st.subheader("My Waiver Requests")

    waivers = []
    for w in all_waivers:
        entry = dict(w)
        if w.get("is_standing"):
            start = w.get("start_date")
            end = w.get("end_date")
            start_str = (
                start.strftime("%Y-%m-%d") if isinstance(start, datetime) else "Unknown"
            )
            end_str = (
                end.strftime("%Y-%m-%d") if isinstance(end, datetime) else "Unknown"
            )
            entry["_event_name"] = "Standing waiver"
            entry["_event_date"] = f"{start_str} → {end_str}"
            waivers.append(entry)
            continue

        record = next(
            (r for r in records if r["_id"] == w.get("attendance_record_id")), None
        )
        if record is None:
            continue
        event = events_by_id.get(record.get("event_id"))
        entry["_event_name"] = event.get("event_name") if event else "Unknown event"
        entry["_event_date"] = (
            event.get("start_date").strftime("%Y-%m-%d")
            if event and isinstance(event.get("start_date"), datetime)
            else "Unknown date"
        )
        waivers.append(entry)

    waivers.sort(key=lambda w: w.get("created_at") or datetime.min, reverse=True)
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

    start_date, end_date, range_complete = parse_streamlit_date_range(
        date_value, default_start, today
    )
    if not range_complete:
        st.info("Select an end date to complete the range (using today for now).")

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
    st.dataframe(df, hide_index=True, width="stretch")

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

    if "selected_waiver_id_value" not in st.session_state:
        st.session_state["selected_waiver_id_value"] = next(
            iter(waiver_by_id.keys()), None
        )
    elif st.session_state["selected_waiver_id_value"] not in waiver_by_id:
        st.session_state["selected_waiver_id_value"] = next(
            iter(waiver_by_id.keys()), None
        )

    selected_id = st.selectbox(
        "Select waiver",
        options=list(waiver_by_id.keys()),
        format_func=_waiver_label,
        index=list(waiver_by_id.keys()).index(
            st.session_state["selected_waiver_id_value"]
        )
        if st.session_state["selected_waiver_id_value"] in waiver_by_id
        else 0,
    )
    st.session_state["selected_waiver_id_value"] = selected_id

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
            st.warning("Type DELETE below to permanently withdraw this waiver.")
            confirmation = st.text_input(
                "Confirm withdrawal", key=f"confirm_input_{waiver_id}"
            )
            c1, c2 = st.columns(2)
            if c1.button("Confirm Withdraw", key=f"yes_{waiver_id}", type="primary"):
                if not confirm_destructive_action(confirmation):
                    st.error("Confirmation text does not match 'DELETE'.")
                else:
                    success = withdraw_waiver(selected["_id"])
                    st.session_state.confirm_withdraw_id = None
                    st.session_state["selected_waiver_id_value"] = waiver_id
                    st.session_state.pop("selected_waiver_id", None)
                    if success:
                        st.session_state.show_success = "Waiver withdrawn successfully."
                    else:
                        st.session_state.show_error = "Failed to withdraw waiver."
                    st.rerun()
            if c2.button("Cancel", key=f"no_{waiver_id}", type="secondary"):
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


def _build_attachments(uploaded_file) -> list[dict]:
    if uploaded_file is None:
        return []
    return [
        {
            "filename": uploaded_file.name,
            "content_type": uploaded_file.type or "application/octet-stream",
            "data": uploaded_file.read(),
        }
    ]


def _build_reason_text(
    common_reasons: list[str], selected_reason: str, extra: str
) -> str:
    if selected_reason == common_reasons[-1]:
        return extra.strip()
    return f"{selected_reason}. {extra}".strip(". ")


def _submit_singular_waiver(
    *,
    user_id: str,
    selected_record: dict,
    reason_text: str,
    waiver_type: str,
    cadre_only: bool,
    attachments: list[dict],
):
    existing = get_waiver_by_attendance_record(selected_record["_id"])
    if (
        existing
        and (existing.get("status") or "").lower() == "denied"
        and bool(existing.get("auto_denied"))
    ):
        became_pending, why = resubmit_auto_denied_waiver(
            existing, selected_record["_id"], reason_text
        )
        if not became_pending:
            st.session_state.show_error = (
                f"Waiver is still invalid and was auto-denied again: {why}"
            )
        else:
            st.session_state.show_success = "Waiver request submitted successfully!"
        st.rerun()

    result = create_waiver(
        attendance_record_id=selected_record["_id"],
        reason=reason_text,
        status="pending",
        submitted_by_user_id=user_id,
        waiver_type=waiver_type,
        cadre_only=cadre_only,
        attachments=attachments,
    )
    if not result:
        st.session_state.show_error = "Failed to submit waiver. Please try again."
        st.rerun()
        return

    created = get_waiver_by_id(result.inserted_id)
    created_status = (created.get("status") if created else "") or ""
    if created_status.lower() == "denied":
        st.session_state.show_error = (
            "Waiver was auto-denied. See notes under your waiver status."
        )
    else:
        if waiver_type == "sickness":
            apply_sickness_auto_approval(result.inserted_id, user_id)
        st.session_state.show_success = "Waiver request submitted successfully!"
    st.rerun()


def _submit_standing_waiver(
    *,
    user_id: str,
    start: date,
    end: date,
    event_types: list[str],
    reason_text: str,
    waiver_type: str,
    cadre_only: bool,
    attachments: list[dict],
):
    is_valid, why = validate_standing_waiver(start, end, event_types)
    if not is_valid:
        st.session_state.show_error = f"Standing waiver invalid: {why}"
        st.rerun()
        return

    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)

    result = create_waiver(
        attendance_record_id=None,
        reason=reason_text,
        status="pending",
        submitted_by_user_id=user_id,
        waiver_type=waiver_type,
        cadre_only=cadre_only,
        attachments=attachments,
        is_standing=True,
        start_date=start_dt,
        end_date=end_dt,
        event_types=event_types,
    )
    if not result:
        st.session_state.show_error = "Failed to submit waiver. Please try again."
    else:
        if waiver_type == "sickness":
            apply_sickness_auto_approval(result.inserted_id, user_id)
        st.session_state.show_success = (
            "Standing waiver request submitted successfully!"
        )
        for key in (
            "waiver_standing_toggle",
            "waiver_standing_range",
            "waiver_standing_event_types",
        ):
            st.session_state.pop(key, None)
    st.rerun()


def waiver_form(
    user_id: str,
    records: list[dict],
    waivers_by_record_id: dict,
    events_by_id: dict,
):
    record_id = st.session_state.waiver_record_id
    st.session_state.waiver_record_id = None

    absent_records = get_absent_records_without_waiver(records, waivers_by_record_id)
    is_standing_mode = st.toggle(
        "Standing waiver (covers a date range)",
        value=False,
        key="waiver_standing_toggle",
        help="Use a standing waiver when you'll be absent for an extended span of PT/LLAB days.",
    )

    if not is_standing_mode and not absent_records:
        st.info("You don't have any absent records to submit a waiver for.")
        return

    record_labels: dict[str, dict] = {}
    default_index = 0
    if not is_standing_mode:
        record_labels = {dropdown_row(r, events_by_id): r for r in absent_records}
        if record_id:
            for i, record in enumerate(absent_records):
                if str(record["_id"]) == record_id:
                    default_index = i
                    break

    today = datetime.now(timezone.utc).date()
    common_reasons = get_common_reasons()

    standing_range = None
    standing_event_types: list[str] = []
    standing_error: str | None = None
    standing_ready = False

    if is_standing_mode:
        standing_range = st.date_input(
            "Standing waiver date range",
            value=(today, today + timedelta(days=7)),
            key="waiver_standing_range",
            help="Inclusive start and end dates. Only PT/LLAB days in the range are covered.",
        )
        standing_event_types = st.multiselect(
            "Event types covered",
            options=["pt", "lab"],
            default=["pt", "lab"],
            format_func=lambda t: {"pt": "PT", "lab": "LLAB"}.get(t, t),
            key="waiver_standing_event_types",
        )

        parsed_start, parsed_end, range_complete = parse_streamlit_date_range(
            standing_range, today, today
        )
        if not range_complete:
            st.info("Select an end date to preview the covered events.")
        elif not standing_event_types:
            standing_error = "Select at least one event type for the standing waiver."
            st.error(standing_error)
        else:
            is_valid, why = validate_standing_waiver(
                parsed_start, parsed_end, standing_event_types
            )
            if not is_valid:
                standing_error = why
                st.error(why)
            else:
                preview = compute_standing_waiver_dates(
                    parsed_start, parsed_end, standing_event_types
                )
                st.caption(f"This waiver would cover {len(preview)} event(s).")
                if preview:
                    preview_rows = [
                        {
                            "Date": p["date"].strftime("%Y-%m-%d"),
                            "Day": p["day"],
                            "Type": p["type"],
                        }
                        for p in preview
                    ]
                    st.dataframe(
                        pd.DataFrame(preview_rows),
                        hide_index=True,
                        width="stretch",
                    )
                standing_ready = True

    with st.form("waiver_form", clear_on_submit=True):
        if is_standing_mode:
            label = ""
        else:
            label = st.selectbox(
                "Select Absent Event",
                options=list(record_labels.keys()),
                index=default_index,
            )

        waiver_type = st.radio(
            "Waiver type",
            options=["non-medical", "medical", "sickness"],
            format_func=lambda x: {
                "non-medical": "Non-Medical",
                "medical": "Medical",
                "sickness": "Sickness",
            }.get(x, x),
            horizontal=True,
        )

        if waiver_type == "sickness":
            st.info(
                "Your first sickness waiver is automatically approved. Subsequent sickness waivers go to cadre for review."
            )

        if waiver_type == "medical":
            st.info(
                "Medical waivers are visible to cadre only (not flight commanders)."
            )

        selected_reason = st.selectbox("Reason", options=common_reasons)
        extra_details = ""
        if selected_reason == common_reasons[-1]:
            extra_details = st.text_area("Describe your reason")
        else:
            extra_details = st.text_area("Additional details (optional)")

        uploaded_file = st.file_uploader(
            "Attach supporting document (optional)",
            type=["pdf", "png", "jpg", "jpeg", "docx"],
        )

        force_cadre_only = resolve_cadre_only(
            waiver_type, uploaded_file is not None, False
        )
        cadre_only = st.checkbox(
            "Send to cadre staff only",
            value=force_cadre_only,
            disabled=force_cadre_only,
        )

        col1, col2, spacer = st.columns([2, 2, 8])
        with col1:
            submit = st.form_submit_button("Submit")
        with col2:
            cancel = st.form_submit_button("Cancel", type="secondary")

    if submit:
        reason_text = _build_reason_text(common_reasons, selected_reason, extra_details)
        if not reason_text:
            st.session_state.show_error = (
                "Please provide a reason for your waiver request."
            )
            st.rerun()
        elif is_standing_mode:
            if standing_error:
                st.session_state.show_error = standing_error
                st.rerun()
            elif not standing_ready:
                st.session_state.show_error = (
                    "Select a complete start and end date for the standing waiver."
                )
                st.rerun()
            else:
                parsed_start, parsed_end, _ = parse_streamlit_date_range(
                    standing_range, today, today
                )
                _submit_standing_waiver(
                    user_id=user_id,
                    start=parsed_start,
                    end=parsed_end,
                    event_types=standing_event_types,
                    reason_text=reason_text,
                    waiver_type=waiver_type,
                    cadre_only=cadre_only,
                    attachments=_build_attachments(uploaded_file),
                )
        else:
            _submit_singular_waiver(
                user_id=user_id,
                selected_record=record_labels[label],
                reason_text=reason_text,
                waiver_type=waiver_type,
                cadre_only=cadre_only,
                attachments=_build_attachments(uploaded_file),
            )

    if cancel:
        st.switch_page("pages/8_Cadet_Attendance.py")


st.title("My Waivers")

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

current_user = get_current_user()
assert current_user is not None

email = current_user["email"]
if not email:
    st.error("Could not find an account with this email.")
    st.stop()

user = require(get_user_by_email(email), "Could not find an account with this email.")

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    if not user_has_any_role(current_user, ["admin"]):
        st.error("No cadet profile found for your account.")
        st.stop()
    cadet = get_temp_cadet()

records, waivers_by_record_id, all_waivers, events_by_id = load_waiver_data(
    cadet["_id"], user["_id"]
)
show_waivers(records, all_waivers, events_by_id)

st.divider()
with st.expander(
    "Submit New Waiver Request", expanded=st.session_state.waiver_record_id is not None
):
    waiver_form(str(user["_id"]), records, waivers_by_record_id, events_by_id)

if st.session_state.show_success:
    st.success(st.session_state.show_success)
    st.session_state.show_success = None
if st.session_state.show_error:
    st.error(st.session_state.show_error)
    st.session_state.show_error = None
