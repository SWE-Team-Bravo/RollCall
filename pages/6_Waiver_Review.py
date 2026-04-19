from __future__ import annotations
import streamlit as st
import pandas as pd

from services.waiver_review import (
    get_flight_options,
    get_waiver_context,
    get_waiver_export_df,
    get_waivers,
    submit_decision,
)
from services.waivers import WAIVER_STATUS_BADGE

from utils.auth import get_current_user, require_role
from utils.db_schema_crud import get_user_by_email
from utils.export import to_excel

from utils.st_helpers import require


STATUS_BADGE = WAIVER_STATUS_BADGE


require_role("admin", "cadre", "flight_commander")
st.title("Waiver Review")
st.caption("Review waiver requests and approve/deny with comments.")

current_user = get_current_user()
assert current_user is not None

approver_email = current_user.get("email", "")
if not approver_email:
    st.error("Missing current user email; cannot record approvals.")
    st.stop()

approver_user = require(
    get_user_by_email(approver_email), "Could not resolve approver user in database."
)
approver_id = approver_user["_id"]

status_filter = st.selectbox(
    "Status", ["all", "pending", "approved", "denied"], index=0
)
flight_filter = st.selectbox("Flight", get_flight_options(), index=0)
cadet_search = st.text_input("Cadet search (name or email)", "").strip().lower()

waivers = get_waivers(status_filter)

if not waivers:
    st.info("No waivers found for the selected filters.")
    st.stop()

rows = []
for waiver in waivers:
    waiver_id = waiver.get("_id")
    if waiver_id is None:
        continue

    ctx = get_waiver_context(waiver)
    if ctx is None:
        continue

    cadet_name = ctx["cadet_name"]
    cadet_email = ctx["cadet_email"]
    flight_name = ctx["flight_name"]
    event_name = ctx["event_name"]
    event_date = ctx["event_date"]
    event_type = ctx["event_type"]
    waiver_status = (waiver.get("status") or "pending").lower()

    if flight_filter != "All flights" and flight_name != flight_filter:
        continue

    if cadet_search:
        hay = f"{cadet_name} {cadet_email}".lower()
        if cadet_search not in hay:
            continue

    rows.append(
        {
            "waiver_id": waiver_id,
            "waiver_status": waiver_status,
            "reason": waiver.get("reason", ""),
            "cadet_name": cadet_name,
            "cadet_email": cadet_email,
            "flight_name": flight_name,
            "event_name": event_name,
            "event_date": event_date,
            "event_type": event_type,
        }
    )

export_df = get_waiver_export_df(rows)
if isinstance(export_df, str):
    st.info(export_df)
    st.stop()

if not rows:
    st.info("No waivers matched the selected filters.")
    st.stop()

for w in rows:
    with st.container(border=True):
        top = st.columns([4, 2, 2])
        top[0].markdown(f"**{w['cadet_name']}**  \n{w['cadet_email']}")
        top[1].markdown(f"**Flight:** {w['flight_name']}")
        top[2].markdown(
            f"**Status:** {STATUS_BADGE.get(w['waiver_status'], w['waiver_status'])}"
        )

        st.write(
            f"**Event:** {w['event_date']} — {w['event_name']} ({w['event_type']})"
        )
        st.write(f"**Cadet reason:** {w['reason']}")

        if w["waiver_status"] == "pending":
            with st.form(f"waiver_decision_{w['waiver_id']}"):
                decision = st.radio(
                    "Decision",
                    ["Approve", "Deny"],
                    horizontal=True,
                    key=f"dec_{w['waiver_id']}",
                )
                comments = st.text_area(
                    "Comments (required for Deny)", key=f"com_{w['waiver_id']}"
                )
                submitted = st.form_submit_button("Submit decision")

            if submitted:
                if decision == "Deny" and not comments.strip():
                    st.error("Please provide comments when denying a waiver.")
                else:
                    success, err = submit_decision(
                        waiver_id=w["waiver_id"],
                        approver_id=approver_id,
                        decision=decision,
                        comments=comments.strip(),
                        cadet_email=w["cadet_email"],
                        event_name=w["event_name"],
                        event_date=w["event_date"],
                    )
                    if success:
                        st.success("Saved.")
                        st.rerun()
                    else:
                        st.error(err)

st.divider()
col1, col2, spacer = st.columns([2, 2, 10])
if isinstance(export_df, pd.DataFrame):
    col1.download_button(
        "Export CSV",
        export_df.to_csv(index=False).encode("utf-8"),
        "waivers.csv",
        "text/csv",
    )
    col2.download_button(
        "Export Excel",
        to_excel(export_df),
        "waivers.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
