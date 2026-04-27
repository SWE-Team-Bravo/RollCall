from __future__ import annotations
from typing import cast
import streamlit as st
import pandas as pd

from services.waiver_review import (
    get_flight_options,
    get_paginated_waiver_review_rows,
    get_waiver_export_df,
    get_waiver_review_rows,
    submit_decision,
)
from services.waivers import WAIVER_STATUS_BADGE

from utils.auth import get_current_user, require_role
from utils.db_schema_crud import get_user_by_email
from utils.export import to_excel
from utils.pagination import (
    init_pagination_state,
    render_pagination_controls,
    sync_pagination_state,
)

from utils.st_helpers import require


STATUS_BADGE = WAIVER_STATUS_BADGE


require_role("admin", "cadre", "waiver_reviewer")
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
    "Status", ["All", "Pending", "Approved", "Denied"], index=0
)

viewer_roles = list(current_user.get("roles") or [])

flight_filter = st.selectbox("Flight", options=get_flight_options(), index=0)
cadet_search = st.text_input("Cadet search (name or email)", "").strip().lower()

pagination_reset_token = "|".join(
    [
        status_filter.lower(),
        flight_filter,
        cadet_search,
        ",".join(sorted(viewer_roles)),
    ]
)
review_page, review_page_size = init_pagination_state(
    "waiver_review",
    reset_token=pagination_reset_token,
)

rows = get_waiver_review_rows(
    status_filter=status_filter.lower(),
    flight_filter=flight_filter,
    cadet_search=cadet_search,
    viewer_roles=viewer_roles,
)
paginated_rows = get_paginated_waiver_review_rows(
    status_filter=status_filter.lower(),
    flight_filter=flight_filter,
    cadet_search=cadet_search,
    viewer_roles=viewer_roles,
    page=review_page,
    page_size=review_page_size,
)
sync_pagination_state("waiver_review", paginated_rows)

export_df = get_waiver_export_df(rows)
if isinstance(export_df, str):
    st.info(export_df)
    st.stop()

if not rows:
    st.info("No waivers matched the selected filters.")
    st.stop()

pending_items = [
    w for w in cast(list, paginated_rows["items"]) if w["waiver_status"] == "pending"
]

if pending_items:
    st.subheader("Bulk Actions")

    pending_df = pd.DataFrame(
        [
            {
                "Selected": False,
                "Cadet": w["cadet_name"],
                "Flight": w["flight_name"],
                "Event": f"{w['event_date']} — {w['event_name']}",
                "Type": w["waiver_type"],
                "Reason": w["reason"],
                "_waiver_id": str(w["waiver_id"]),
            }
            for w in pending_items
        ]
    )

    edited_df = st.data_editor(
        pending_df.drop(columns=["_waiver_id"]),
        column_config={
            "Selected": st.column_config.CheckboxColumn("Selected", default=False)
        },
        hide_index=True,
        width="stretch",
        key="bulk_waiver_select",
    )

    selected_indexes = edited_df[
        edited_df.get("Selected", pd.Series([False] * len(edited_df)))
    ].index.tolist()
    selected_waiver_ids = [pending_df.iloc[i]["_waiver_id"] for i in selected_indexes]

    if selected_waiver_ids:
        col1, col2 = st.columns([3, 5])
        bulk_decision = col1.radio(
            "Bulk Decision", ["Approve", "Deny"], horizontal=True
        )
        bulk_comments = col2.text_input("Comments (required for Deny)")

        if st.button("Apply to Selected", type="primary"):
            if bulk_decision == "Deny" and not bulk_comments.strip():
                st.error("please provide comments when denying waivers.")
            else:
                success_count = 0
                fail_count = 0
                for w_id in selected_waiver_ids:
                    w = next(
                        (x for x in pending_items if str(x["waiver_id"]) == w_id), None
                    )
                    if w is None:
                        continue
                    ok, msg = submit_decision(
                        waiver_id=w["waiver_id"],
                        approver_id=approver_id,
                        decision=bulk_decision,
                        comments=bulk_comments.strip(),
                        cadet_email=w["cadet_email"],
                        event_name=w["event_name"],
                        event_date=w["event_date"],
                    )
                    if ok:
                        success_count += 1
                        if msg:
                            st.warning(msg)
                    else:
                        fail_count += 1
                st.success(f"Applied to {success_count} waiver(s).")
                if fail_count:
                    st.error(f"{fail_count} waiver(s) failed.")
                st.rerun()

st.divider()

for w in cast(list, paginated_rows["items"]):
    with st.container(border=True):
        top = st.columns([4, 2, 2])
        top[0].markdown(f"**{w['cadet_name']}**  \n{w['cadet_email']}")
        top[1].markdown(f"**Flight:** {w['flight_name']}")
        top[2].markdown(
            f"**Status:** {STATUS_BADGE.get(w['waiver_status'], w['waiver_status'])}"
        )

        type_label = {
            "medical": "Medical",
            "non-medical": "Non-Medical",
            "sickness": "Sickness",
        }.get(w["waiver_type"], w["waiver_type"])
        st.write(
            f"**Event:** {w['event_date']} — {w['event_name']} ({w['event_type']})  |  **Type:** {type_label}"
        )
        st.write(f"**Cadet reason:** {w['reason']}")
        for att in w.get("attachments") or []:
            file_data = att.get("data")
            if file_data:
                st.download_button(
                    label=f"Download: {att.get('filename', 'attachment')}",
                    data=bytes(file_data),
                    file_name=att.get("filename", "attachment"),
                    mime=att.get("content_type", "application/octet-stream"),
                    key=f"att_{w['waiver_id']}_{att.get('filename', '')}",
                )

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
                        if err:
                            st.warning(err)
                        st.rerun()
                    else:
                        st.error(err)

st.divider()
render_pagination_controls("waiver_review", paginated_rows)

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
