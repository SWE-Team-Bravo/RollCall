from __future__ import annotations

from datetime import datetime

import streamlit as st

from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    create_waiver_approval,
    get_all_flights,
    get_all_waivers,
    get_attendance_record_by_id,
    get_cadet_by_id,
    get_event_by_id,
    get_flight_by_id,
    get_user_by_email,
    get_user_by_id,
    update_waiver,
)

STATUS_BADGE = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "denied": "🔴 Denied",
}


def _fmt_date(dt: object) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return "Unknown date"


require_role("admin", "cadre", "flight_commander")
st.title("Waiver Review")
st.caption("Review waiver requests and approve/deny with comments.")

current_user = get_current_user()
assert current_user is not None

approver_email = current_user.get("email", "")
if not approver_email:
    st.error("Missing current user email; cannot record approvals.")
    st.stop()

approver_user = get_user_by_email(approver_email)
if approver_user is None:
    st.error("Could not resolve approver user in database.")
    st.stop()
assert approver_user is not None
approver_id = approver_user["_id"]

# --- Filters UI
status_filter = st.selectbox(
    "Status", ["pending", "approved", "denied", "all"], index=0
)

flights = get_all_flights()
flight_names = ["All flights"] + [f.get("name", "Unnamed flight") for f in flights]
flight_filter = st.selectbox("Flight", flight_names, index=0)

cadet_search = st.text_input("Cadet search (name or email)", "").strip().lower()

waivers = get_all_waivers()
if status_filter != "all":
    waivers = [w for w in waivers if (w.get("status") or "").lower() == status_filter]

waivers.sort(key=lambda w: w.get("created_at") or datetime.min, reverse=True)

if not waivers:
    st.info("No waivers found for the selected filters.")
    st.stop()

shown_any = False

for waiver in waivers:
    waiver_id = waiver.get("_id")
    if waiver_id is None:
        continue

    waiver_status = (waiver.get("status") or "pending").lower()

    attendance_record_id = waiver.get("attendance_record_id")
    if attendance_record_id is None:
        continue

    record = get_attendance_record_by_id(attendance_record_id)
    if record is None:
        continue

    # Event
    event = None
    event_id = record.get("event_id")
    if event_id is not None:
        event = get_event_by_id(event_id)

    # Cadet
    cadet = None
    cadet_id = record.get("cadet_id")
    if cadet_id is not None:
        cadet = get_cadet_by_id(cadet_id)

    # User
    user = None
    if cadet is not None:
        user_id = cadet.get("user_id")
        if user_id is not None:
            user = get_user_by_id(user_id)

    cadet_name = user.get("name") if user else "Unknown cadet"
    cadet_email = user.get("email") if user else ""

    # Flight
    flight_name = "Unassigned"
    if cadet is not None:
        cadet_flight_id = cadet.get("flight_id")
        if cadet_flight_id is not None:
            flight = get_flight_by_id(cadet_flight_id)
            if flight:
                flight_name = flight.get("name", "Unassigned")

    # apply flight filter
    if flight_filter != "All flights" and flight_name != flight_filter:
        continue

    # apply cadet search filter
    if cadet_search:
        hay = f"{cadet_name} {cadet_email}".lower()
        if cadet_search not in hay:
            continue

    shown_any = True

    event_name = event.get("event_name") if event else "Unknown event"
    event_date = _fmt_date(event.get("start_date") if event else None)
    event_type = (event.get("event_type") if event else "") or "unknown"

    with st.container(border=True):
        top = st.columns([4, 2, 2])
        top[0].markdown(f"**{cadet_name}**  \n{cadet_email}")
        top[1].markdown(f"**Flight:** {flight_name}")
        top[2].markdown(f"**Status:** {STATUS_BADGE.get(waiver_status, waiver_status)}")

        st.write(f"**Event:** {event_date} — {event_name} ({event_type})")
        st.write(f"**Cadet reason:** {waiver.get('reason', '')}")

        if waiver_status == "pending":
            with st.form(f"waiver_decision_{waiver_id}"):
                decision = st.radio(
                    "Decision",
                    ["Approve", "Deny"],
                    horizontal=True,
                    key=f"dec_{waiver_id}",
                )
                comments = st.text_area(
                    "Comments (required for Deny)",
                    key=f"com_{waiver_id}",
                )
                submitted = st.form_submit_button("Submit decision")

            if submitted:
                if decision == "Deny" and not comments.strip():
                    st.error("Please provide comments when denying a waiver.")
                else:
                    new_status = "approved" if decision == "Approve" else "denied"
                    upd = update_waiver(waiver_id, {"status": new_status})

                    if upd is None:
                        st.error("Failed to update waiver status.")
                    else:
                        appr = create_waiver_approval(
                            waiver_id=waiver_id,
                            approver_id=approver_id,
                            decision=new_status,
                            comments=comments.strip() or "Approved.",
                        )
                        if appr is None:
                            st.error("Failed to create waiver approval record.")
                        else:
                            st.success("Saved.")
                            st.rerun()

if not shown_any:
    st.info("No waivers matched the selected filters.")
