import streamlit as st
import pandas as pd

from utils.at_risk_email import send_at_risk_emails
from utils.auth import require_role
from utils.export import to_excel

from services.at_risk_cadets import get_df

require_role("admin", "cadre", "flight_commander")

st.title("At-Risk Cadets Report")

df = get_df()
if isinstance(df, str):
    st.warning("No cadets found.")
elif isinstance(df, pd.DataFrame):
    col1, col2, col3, spacer = st.columns([2, 2, 4, 8])
    col1.download_button(
        "Export CSV",
        df.to_csv(index=False).encode("utf-8"),
        "at_risk_cadets.csv",
        "text/csv",
    )
    col2.download_button(
        "Export Excel",
        to_excel(df),
        "at_risk_cadets.xlsx",
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

    st.dataframe(df, hide_index=True, width="stretch")
