import streamlit as st
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    get_attendance_by_cadet,
    get_cadet_by_user_id,
    get_event_by_id,
    get_flight_by_id,
    get_user_by_email,
    get_waiver_by_attendance_record,
)
from services.cadet_attendance import (
    cadet_attendance,
    count_absences,
    filter_rows,
    get_cadet_flight_label,
)


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


def load_attendance_db(cadet_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    records = get_attendance_by_cadet(cadet_id)

    events = []
    waivers = []
    for record in records:
        if record.get("event_id"):
            event = get_event_by_id(record["event_id"])
            if event:
                events.append(event)
        waiver = get_waiver_by_attendance_record(record["_id"])
        if waiver:
            waivers.append(waiver)

    return records, events, waivers


def show_risk_banner(pt_absences: int, llab_absences: int):
    if pt_absences >= PT_ABSENCE_THRESHOLD:
        st.error(
            f"**At Risk** — You have reached the absence threshold for "
            f"PT Absences ({pt_absences}/{PT_ABSENCE_THRESHOLD}). Contact your cadre immediately."
        )
    elif llab_absences >= LLAB_ABSENCE_THRESHOLD:
        st.error(
            f"**At Risk** — You have reached the absence threshold for: "
            f"LLAB Absences ({llab_absences}/{LLAB_ABSENCE_THRESHOLD}). Contact your cadre immediately."
        )
    elif (
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


def show_attendance_row(row: dict):
    date = row["start_date"].strftime("%Y-%m-%d") if row["start_date"] else "—"

    h1, h2, h3, h4, h5 = st.columns([3, 2, 1, 2, 2])
    h1.write(row["event_name"])
    h2.write(date)
    h3.write(row["event_type"])
    h4.write(STATUS_BADGE.get(row["status"], row["status"].capitalize()))

    if row["waiver_status"]:
        h5.write(
            WAIVER_BADGE.get(row["waiver_status"], row["waiver_status"].capitalize())
        )
    elif row["status"] == "absent" and row["waiver_eligible"]:
        if h5.button("Request Waiver", key=f"waiver_{row['record_id']}"):
            st.session_state["waiver_record_id"] = row["record_id"]
            st.switch_page("pages/5_Waivers.py")
    else:
        h5.write("—")

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

    h1, h2, h3, h4, h5 = st.columns([3, 2, 1, 2, 2])
    h1.markdown("**Event**")
    h2.markdown("**Date**")
    h3.markdown("**Type**")
    h4.markdown("**Status**")
    h5.markdown("**Waiver**")
    st.divider()

    for row in filtered:
        show_attendance_row(row)


def show_header(cadet: dict, current_user: dict):
    flights = []
    if cadet.get("flight_id"):
        flight = get_flight_by_id(cadet["flight_id"])
        if flight:
            flights = [flight]
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

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    st.error("You must be a cadet to view attendance.")
    st.stop()
assert cadet is not None

records, events, waivers = load_attendance_db(cadet["_id"])
rows = cadet_attendance(records, events, waivers)

show_header(cadet, current_user)

st.subheader("Absence Summary")
show_absence_summary(rows)

st.subheader("Attendance Records")
show_attendance_table(rows)
