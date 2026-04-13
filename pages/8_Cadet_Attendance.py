import streamlit as st
import pandas as pd
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    get_cadet_by_user_id,
    get_user_by_email,
)
from services.cadet_attendance import (
    load_attendance_db,
    load_cadet_flights,
    cadet_attendance,
    count_absences,
    filter_rows,
    get_cadet_flight_label,
)
from utils.auth_logic import user_has_any_role
from scripts.demo_admin import get_temp_cadet

PT_ABSENCE_THRESHOLD = 9
LLAB_ABSENCE_THRESHOLD = 2

STATUS_BADGE = {
    "present": "🟢 Present",
    "absent": "🔴 Absent",
    "excused": "🟡 Excused",
    "waived": "🟡 Excused",
}

WAIVER_BADGE = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
}


def show_risk_banner(pt_absences: int, llab_absences: int):
    at_risk = False
    if pt_absences >= PT_ABSENCE_THRESHOLD:
        st.error(
            f"**At Risk** — You have reached the absence threshold for "
            f"PT. Absences ({pt_absences}/{PT_ABSENCE_THRESHOLD}). Contact your cadre immediately."
        )
        at_risk = True
    if llab_absences >= LLAB_ABSENCE_THRESHOLD:
        st.error(
            f"**At Risk** — You have reached the absence threshold for: "
            f"LLAB. Absences ({llab_absences}/{LLAB_ABSENCE_THRESHOLD}). Contact your cadre immediately."
        )
        at_risk = True
    if not at_risk:
        if (
            pt_absences == PT_ABSENCE_THRESHOLD - 1
            or llab_absences == LLAB_ABSENCE_THRESHOLD - 1
        ):
            st.warning(
                "**Caution** — You are one absence away from the limit for one or more event types."
            )
        else:
            st.success("Attendance is within acceptable limits.")


def show_absence_summary(rows: list[dict]):
    pt_absences = count_absences(rows, "pt")
    llab_absences = count_absences(rows, "lab")
    total_records = len(rows)
    present_count = sum(1 for r in rows if r["status"] == "present")
    attendance_rate = round(present_count / total_records * 100) if total_records else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Attendance Rate", f"{attendance_rate}%")
    col2.metric("Total Events", total_records)

    pt_remaining = PT_ABSENCE_THRESHOLD - pt_absences
    col3.metric(
        "PT Absences",
        f"{pt_absences} / {PT_ABSENCE_THRESHOLD}",
        delta=f"{pt_remaining} remaining" if pt_remaining > 0 else "At limit",
        delta_color="normal" if pt_remaining > 0 else "inverse",
    )

    llab_remaining = LLAB_ABSENCE_THRESHOLD - llab_absences
    col4.metric(
        "LLAB Absences",
        f"{llab_absences} / {LLAB_ABSENCE_THRESHOLD}",
        delta=f"{llab_remaining} remaining" if llab_remaining > 0 else "At limit",
        delta_color="normal" if llab_remaining > 0 else "inverse",
    )
    show_risk_banner(pt_absences, llab_absences)
    st.divider()


def show_attendance_table(rows: list[dict]):
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox(
            "Filter by status",
            ["All", "Present", "Absent", "Excused"],
        )
    with col2:
        filter_type = st.selectbox(
            "Filter by event type",
            ["All", "PT", "LLAB"],
        )

    filtered = filter_rows(rows, filter_status, filter_type)
    if not filtered:
        st.info("No records to match the current filter.")
        return

    table_rows: list[dict[str, str]] = []
    eligible: list[dict] = []

    for row in filtered:
        date_str = row["start_date"].strftime("%Y-%m-%d") if row["start_date"] else "—"
        status_label = STATUS_BADGE.get(row["status"], row["status"].capitalize())

        waiver_label = "—"
        if row.get("waiver_status"):
            waiver_label = WAIVER_BADGE.get(
                row["waiver_status"], row["waiver_status"].capitalize()
            )
        elif row.get("status") == "absent" and bool(row.get("waiver_eligible")):
            waiver_label = "Eligible"
            eligible.append(row)

        table_rows.append(
            {
                "Event": str(row.get("event_name", "") or ""),
                "Date": date_str,
                "Type": str(row.get("event_type", "") or ""),
                "Status": str(status_label),
                "Waiver": str(waiver_label),
            }
        )

    df = pd.DataFrame(
        table_rows,
        columns=pd.Index(["Event", "Date", "Type", "Status", "Waiver"]),
    )
    st.dataframe(df, hide_index=True, width='stretch')

    st.divider()

    if eligible:
        if "selected_waiver_record_id" not in st.session_state:
            st.session_state.selected_waiver_record_id = str(
                eligible[0].get("record_id")
            )

        eligible_by_id = {
            str(r.get("record_id")): r for r in eligible if r.get("record_id")
        }
        options = list(eligible_by_id.keys())

        if st.session_state.selected_waiver_record_id not in eligible_by_id:
            st.session_state.selected_waiver_record_id = options[0]

        def _label(record_id: str) -> str:
            r = eligible_by_id.get(record_id, {})
            d = r.get("start_date")
            ds = d.strftime("%Y-%m-%d") if d else "—"
            ev = str(r.get("event_name", "") or "").strip() or "Event"
            return f"{ds} — {ev}".strip()

        selected_record_id = st.selectbox(
            "Select event to request waiver",
            options=options,
            format_func=_label,
            key="selected_waiver_record_id",
        )

        if st.button("Request Waiver", key="request_waiver_selected"):
            st.session_state["waiver_record_id"] = selected_record_id
            st.switch_page("pages/5_Waivers.py")
    else:
        st.caption("No eligible absent records for waiver request in the current view.")


def show_header(cadet: dict, current_user: dict):
    flights = load_cadet_flights(cadet)
    flight_label = get_cadet_flight_label(cadet, flights)
    full_name = f"{cadet.get('rank', '')} {current_user['first_name']} {current_user['last_name']}".strip()
    st.markdown(f"##### {full_name}  ·  Flight: {flight_label}")
    st.divider()


require_role("cadet")

st.title("My Attendance")
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

records, events, waivers = load_attendance_db(cadet["_id"])
rows = cadet_attendance(records, events, waivers)

show_header(cadet, current_user)

st.subheader("Absence Summary")
show_absence_summary(rows)

st.subheader("Attendance Records")
show_attendance_table(rows)
