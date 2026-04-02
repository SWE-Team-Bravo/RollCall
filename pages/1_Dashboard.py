from __future__ import annotations

import pandas as pd
import streamlit as st

from services.dashboard import build_attendance_grid
from utils.auth import require_role
from utils.db import get_collection, get_db
from utils.at_risk_email import send_at_risk_emails


def _cell_style(val: str) -> str:
    if val == "P":
        return "background-color: #7FE08A; color: #0b2e13; font-weight: 700; text-align: center;"
    if val == "A":
        return "background-color: #E07F7F; color: #2b0b0b; font-weight: 700; text-align: center;"
    if val == "E":
        return "background-color: #E0D27F; color: #2b240b; font-weight: 700; text-align: center;"
    return "text-align: center;"


require_role("admin", "cadre", "flight_commander")

st.title("Dashboard")
st.caption("Rows = event dates (newest first). Columns = cadets (alphabetical).")

db = get_db()
if db is None:
    st.warning("Database is not configured as of now.")
    st.stop()

users_col = get_collection("users")
cadets_col = get_collection("cadets")
events_col = get_collection("events")
attendance_col = get_collection("attendance_records")

if any(x is None for x in (users_col, cadets_col, events_col, attendance_col)):
    st.error("Database unavailable.")
    st.stop()

assert users_col is not None
assert cadets_col is not None
assert events_col is not None
assert attendance_col is not None

cadet_docs = list(cadets_col.find({}, {"_id": 1, "user_id": 1}))
if not cadet_docs:
    st.info("No cadets found yet.")
    st.stop()

user_ids = [c["user_id"] for c in cadet_docs if "user_id" in c]
user_docs = list(
    users_col.find(
        {"_id": {"$in": user_ids}}, {"_id": 1, "first_name": 1, "last_name": 1}
    )
)

event_docs = list(events_col.find({}, {"_id": 1, "start_date": 1, "event_name": 1}))
if not event_docs:
    st.info("No events found yet.")
    st.stop()

event_ids = [e["_id"] for e in event_docs]
record_docs = list(
    attendance_col.find(
        {"event_id": {"$in": event_ids}},
        {"_id": 0, "event_id": 1, "cadet_id": 1, "status": 1},
    )
)

event_row_labels, cadet_names, grid_rows = build_attendance_grid(
    cadet_docs, user_docs, event_docs, record_docs
)

df = pd.DataFrame(
    grid_rows,
    index=pd.Index(event_row_labels),
    columns=pd.Index(cadet_names),
)

st.dataframe(df.style.applymap(_cell_style), width="stretch")

st.divider()
st.subheader("Legend")

col1, col2, col3 = st.columns(3)
with col1:
    st.success("P = Present")
with col2:
    st.error("A = Absent")
with col3:
    st.warning("E = Excused / Waived")

st.divider()
st.subheader("At-Risk Report")
if st.button("Send At-Risk Emails"):
    sent, failed = send_at_risk_emails()
    if sent == 0 and failed == 0:
        st.info("At-risk cadets not found.")
    elif failed == 0:
        st.success(f"Emails sent to {sent} recipient(s).")
    else:
        st.warning(f"Sent: {sent}; Failed: {failed}.")
