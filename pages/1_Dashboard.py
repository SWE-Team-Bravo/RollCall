from __future__ import annotations

import streamlit as st
import pandas as pd

from services.dashboard import get_df
from utils.auth import require_role
from utils.at_risk_email import send_at_risk_emails
from utils.export import to_excel


def _cell_style(val: str) -> str:
    if val == "P":
        return "background-color: #7FE08A; color: #0b2e13; font-weight: 700; text-align: center;"
    if val == "A":
        return "background-color: #E07F7F; color: #2b0b0b; font-weight: 700; text-align: center;"
    if val == "E":
        return "background-color: #E0D27F; color: #2b240b; font-weight: 700; text-align: center;"
    return "text-align: center;"


require_role("admin", "cadre", "flight_commander")

df = get_df()
if isinstance(df, str):
    st.warning(df)
    st.stop()

st.title("Dashboard")

col1, col2, col3, spacer = st.columns([2, 2, 4, 8])
if isinstance(df, pd.DataFrame):
    col1.download_button(
        "Export CSV", df.to_csv().encode("utf-8"), "attendance.csv", "text/csv"
    )
    col2.download_button(
        "Export Excel",
        to_excel(df),
        "attendance.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
if col3.button("Send At-Risk Emails"):
    sent, failed = send_at_risk_emails()
    if sent == 0 and failed == 0:
        st.info("At-risk cadets not found.")
    elif failed == 0:
        st.success(f"Emails sent to {sent} recipient(s).")
    else:
        st.warning(f"Sent: {sent}; Failed: {failed}.")


st.caption("Rows = event dates (newest first). Columns = cadets (alphabetical).")

assert isinstance(df, pd.DataFrame)
st.dataframe(df.style.map(_cell_style), width="stretch")

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
