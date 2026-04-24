from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from services.audit_log_viewer import (
    build_audit_detail_rows,
    build_audit_overview_row,
    build_audit_table_row,
    export_audit_log_to_df,
    get_audit_activity_options,
    get_audit_detail_columns,
    query_audit_log,
)
from utils.auth import require_role
from utils.export import to_excel
from utils.pagination import (
    init_pagination_state,
    render_pagination_controls,
    sync_pagination_state,
)

require_role("admin")

st.title("Audit Log")
st.caption("Review all data changes across the application.")

# ── Filters ──────────────────────────────────────────────────────────────────

st.subheader("Filters")

f1, f2, f3 = st.columns(3)
with f1:
    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=7)
    start_date = st.date_input("Start date", value=default_start)
with f2:
    end_date = st.date_input("End date", value=today)
with f3:
    actor_search_filter = st.text_input(
        "Actor search", value="", placeholder="Name, email, or ID"
    )

f4, f5 = st.columns([2, 1])
with f4:
    activity_filter = st.multiselect(
        "Activity",
        options=get_audit_activity_options(),
        help="Leave blank to show everything.",
        placeholder="Everything",
    )
with f5:
    target_search = st.text_input(
        "Target search", value="", placeholder="Target or cadet"
    )

# Build reset token from filters
reset_token = "|".join(
    [
        str(start_date),
        str(end_date),
        ",".join(activity_filter),
        actor_search_filter.strip().lower(),
        target_search.strip().lower(),
    ]
)

# ── Query ────────────────────────────────────────────────────────────────────

page, page_size = init_pagination_state(
    "audit_log",
    reset_token=reset_token,
)

start_dt = datetime.combine(start_date, datetime.min.time()).replace(
    tzinfo=timezone.utc
)
end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

result = query_audit_log(
    start_date=start_dt,
    end_date=end_dt,
    activities=activity_filter if activity_filter else None,
    actor_search=actor_search_filter.strip() or None,
    target_search=target_search.strip() or None,
    page=page,
    page_size=page_size,
)

sync_pagination_state("audit_log", result)

st.caption(f"Showing {len(result['items'])} of {result['total_count']} total entries")

# ── Table ────────────────────────────────────────────────────────────────────

if not result["items"]:
    st.info("No audit entries match the selected filters.")
else:
    st.caption("Select a row to view the full detail table below.")

    df = pd.DataFrame(
        [build_audit_table_row(row, include_audit_id=True) for row in result["items"]]
    )

    selected = st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "Timestamp": st.column_config.TextColumn(disabled=True),
            "Actor": st.column_config.TextColumn(disabled=True),
            "Activity": st.column_config.TextColumn(disabled=True),
            "Target": st.column_config.TextColumn(disabled=True),
            "Cadet": st.column_config.TextColumn(disabled=True),
            "Summary": st.column_config.TextColumn(disabled=True),
            "_audit_id": None,
        },
        key="audit_log_table",
        on_select="rerun",
        selection_mode="single-row",
    )

    render_pagination_controls("audit_log", result)

    # ── Detail Panel ─────────────────────────────────────────────────────────

    selected_rows: list[int] = []
    if isinstance(selected, dict):
        selected_rows = list(selected.get("selection", {}).get("rows", []))
    else:
        selection_data = getattr(selected, "selection", None)
        if selection_data is not None:
            if isinstance(selection_data, dict):
                selected_rows = list(selection_data.get("rows", []))
            else:
                selected_rows = list(getattr(selection_data, "rows", []) or [])

    if selected_rows:
        selected_index = selected_rows[0]
        if 0 <= selected_index < len(result["items"]):
            row = result["items"][selected_index]
            overview_row = build_audit_overview_row(row)
            detail_rows = build_audit_detail_rows(row)

            with st.container(border=True):
                st.subheader("Entry Details")
                st.dataframe(
                    pd.DataFrame([overview_row]),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        column: st.column_config.TextColumn(disabled=True)
                        for column in overview_row
                    },
                )

                if detail_rows:
                    detail_columns = get_audit_detail_columns(detail_rows)

                    st.markdown("**Field Details**")
                    st.dataframe(
                        pd.DataFrame(detail_rows)[detail_columns],
                        hide_index=True,
                        width="stretch",
                        column_config={
                            column: st.column_config.TextColumn(disabled=True)
                            for column in detail_columns
                        },
                    )
                else:
                    st.caption("No additional field-level details for this entry.")
    else:
        st.caption("Select one row above to open the full detail table.")

    # ── Export ───────────────────────────────────────────────────────────────

    st.divider()
    export_df = export_audit_log_to_df(
        start_date=start_dt,
        end_date=end_dt,
        activities=activity_filter if activity_filter else None,
        actor_search=actor_search_filter.strip() or None,
        target_search=target_search.strip() or None,
    )

    if export_df is not None and not export_df.empty:
        c1, c2 = st.columns([1, 4])
        with c1:
            st.download_button(
                "Export CSV",
                export_df.to_csv(index=False).encode("utf-8"),
                "audit_log.csv",
                "text/csv",
            )
        with c2:
            excel_bytes = to_excel(export_df)
            if excel_bytes:
                st.download_button(
                    "Export Excel",
                    excel_bytes,
                    "audit_log.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    else:
        st.caption("No data to export.")
