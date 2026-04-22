import streamlit as st
import pandas as pd

from utils.at_risk_email import send_at_risk_emails
from utils.auth import get_current_user, require_role
from utils.export import to_excel
from utils.db import get_collection

from services.at_risk_cadets import get_df, get_waiver_flag_df, WAIVER_FLAG_THRESHOLD

require_role("admin", "cadre", "flight_commander")

st.title("At-Risk Cadets Report")

current_user = get_current_user()
roles = set((current_user or {}).get("roles", []))
is_fc_only = "flight_commander" in roles and not (roles & {"admin", "cadre"})

fc_flight_id = None
if is_fc_only and current_user:
    users_col = get_collection("users")
    cadets_col = get_collection("cadets")
    if users_col and cadets_col:
        user_doc = users_col.find_one({"email": current_user.get("email")}, {"_id": 1})
        if user_doc:
            cadet_doc = cadets_col.find_one(
                {"user_id": user_doc["_id"]}, {"flight_id": 1}
            )
            if cadet_doc:
                fc_flight_id = cadet_doc.get("flight_id")

df = get_df(flight_id=fc_flight_id)
if isinstance(df, str):
    st.info("No cadets found.")
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

    st.divider()
    st.dataframe(df, hide_index=True, width="stretch")

st.divider()
st.subheader(f"Waiver-Flagged Cadets ({WAIVER_FLAG_THRESHOLD}+ approved waivers)")
waiver_df = get_waiver_flag_df()
if isinstance(waiver_df, str):
    st.info(waiver_df)
else:
    st.dataframe(waiver_df, hide_index=True, width="stretch")
