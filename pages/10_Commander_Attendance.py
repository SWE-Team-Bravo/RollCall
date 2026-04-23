from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from services.attendance_modifications import (
    apply_bulk_attendance_changes,
    build_recent_changes_table,
    get_event_change_history,
    get_selected_change_id,
    get_selected_change_item,
    redo_change,
    undo_change,
)
from services.commander_attendance import build_commander_roster, hydrate_cadet_names
from services.events import closest_event_index, get_all_events, has_event_ended
from utils.auth import get_current_user, require_role
from utils.st_helpers import require
from utils.attendance_status import (
    NO_RECORD_STATUS_LABEL,
    get_attendance_status_cell_style,
    get_attendance_status_label,
)
from utils.db_schema_crud import (
    get_all_cadets,
    get_attendance_by_event,
    get_user_by_email,
    get_users_by_ids,
)

STATUS_OPTIONS = [NO_RECORD_STATUS_LABEL, "Present", "Absent", "Excused"]
STATUS_TO_DB = {"Present": "present", "Absent": "absent", "Excused": "excused"}
HISTORY_PAGE_SIZE = 10

require_role("admin", "cadre")
st.title("Modify Attendance")
st.caption("Manually set attendance for cadets. These entries override self-check-ins.")


def _set_feedback(kind: str, message: str) -> None:
    st.session_state["_attendance_feedback"] = {"kind": kind, "message": message}


def _show_feedback() -> None:
    feedback = st.session_state.pop("_attendance_feedback", None)
    if not feedback:
        return

    kind = str(feedback.get("kind", "info") or "info")
    message = str(feedback.get("message", "") or "").strip()
    if not message:
        return

    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def _sync_history_state(event_id: str) -> None:
    previous_event_id = st.session_state.get("_attendance_history_event_id")
    if previous_event_id == event_id:
        return

    st.session_state["_attendance_history_event_id"] = event_id
    st.session_state["_attendance_history_page"] = 1
    st.session_state["_attendance_selected_change_id"] = None
    st.session_state["_attendance_recent_changes_table_version"] = 0
    st.session_state["_attendance_recent_changes_feedback"] = None


def _recent_changes_table_key() -> str:
    version = int(
        st.session_state.get("_attendance_recent_changes_table_version", 0) or 0
    )
    return f"attendance_recent_changes_table_{version}"


def _reset_recent_changes_selection() -> None:
    st.session_state["_attendance_selected_change_id"] = None
    st.session_state["_attendance_recent_changes_table_version"] = (
        int(st.session_state.get("_attendance_recent_changes_table_version", 0) or 0)
        + 1
    )


def _set_recent_changes_feedback(kind: str, message: str) -> None:
    st.session_state["_attendance_recent_changes_feedback"] = {
        "kind": kind,
        "message": message,
    }


def _clear_recent_changes_feedback() -> None:
    st.session_state["_attendance_recent_changes_feedback"] = None


def _show_recent_changes_feedback() -> None:
    feedback = st.session_state.get("_attendance_recent_changes_feedback")
    if not feedback:
        return

    kind = str(feedback.get("kind", "info") or "info")
    message = str(feedback.get("message", "") or "").strip()
    if not message:
        return

    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


_show_feedback()

current_user = get_current_user()
assert current_user is not None

email = str(current_user.get("email", "")).strip()
user = require(get_user_by_email(email), "Could not find your account.")

all_events = get_all_events()
if not all_events:
    st.info("No events found.")
    st.stop()


def _event_label(event: dict[str, Any]) -> str:
    name = str(event.get("event_name", "Event")).strip() or "Event"
    start = event.get("start_date")
    if isinstance(start, datetime):
        date_str = start.date().isoformat()
    elif isinstance(start, str):
        date_str = start[:10]
    else:
        date_str = ""
    return f"{name} ({date_str})" if date_str else name


selected_event = st.selectbox(
    "Select event",
    options=all_events,
    format_func=_event_label,
    index=closest_event_index(all_events),
)
if selected_event is None:
    st.stop()

event_id: str = selected_event["_id"]
event_has_ended = has_event_ended(selected_event)
default_status = "Absent" if event_has_ended else NO_RECORD_STATUS_LABEL
_sync_history_state(str(event_id))

all_cadets = get_all_cadets()
if not all_cadets:
    st.info("No cadets found.")
    st.stop()

cadet_user_ids = [c["user_id"] for c in all_cadets if c.get("user_id") is not None]
user_by_id = {user["_id"]: user for user in get_users_by_ids(cadet_user_ids)}
all_cadets = hydrate_cadet_names(all_cadets, user_by_id)

records = get_attendance_by_event(event_id)
roster = build_commander_roster(all_cadets, records)

cadet_ids = [str(entry["cadet"]["_id"]) for entry in roster]
initial_statuses = [
    get_attendance_status_label(entry["current_status"], default=default_status)
    for entry in roster
]

df = pd.DataFrame(
    {
        "Cadet": [
            str(e["cadet"].get("name", "") or "").strip()
            or f"{str(e['cadet'].get('last_name', '') or '').strip()}, "
            f"{str(e['cadet'].get('first_name', '') or '').strip()}".strip(", ")
            or "Unknown"
            for e in roster
        ],
        "Current Status": initial_statuses,
        "Set Status": initial_statuses,
    }
)

styler = df.style
if hasattr(styler, "map"):
    styler = styler.map(get_attendance_status_cell_style, subset=["Current Status"])
else:
    styler = styler.applymap(
        get_attendance_status_cell_style,
        subset=["Current Status"],
    )

edited = st.data_editor(
    styler,
    column_config={
        "Cadet": st.column_config.TextColumn(disabled=True),
        "Current Status": st.column_config.TextColumn(disabled=True),
        "Set Status": st.column_config.SelectboxColumn(
            options=STATUS_OPTIONS, required=True
        ),
    },
    hide_index=True,
    width="stretch",
)

st.divider()
if st.button("Save All", type="primary"):
    invalid_no_record_rows = [
        roster[idx]["cadet"]
        for idx, (_, row) in enumerate(edited.iterrows())
        if row["Set Status"] == NO_RECORD_STATUS_LABEL
        and roster[idx]["record"] is not None
    ]
    if invalid_no_record_rows:
        st.error(
            "No Record can only be used for cadets who do not already have an attendance entry."
        )
        st.stop()

    new_statuses = {
        cadet_ids[idx]: STATUS_TO_DB[row["Set Status"]]
        for idx, (_, row) in enumerate(edited.iterrows())
        if row["Set Status"] != initial_statuses[idx]
        and row["Set Status"] in STATUS_TO_DB
    }
    save_result = apply_bulk_attendance_changes(
        event_id=event_id,
        roster=roster,
        new_statuses=new_statuses,
        recorded_by_user_id=user["_id"],
        recorded_by_roles=list(user.get("roles", [])),
    )
    if save_result["changed_count"] == 0:
        _set_feedback("info", "No attendance changes to save.")
    else:
        st.session_state["_attendance_history_page"] = 1
        _reset_recent_changes_selection()
        _clear_recent_changes_feedback()
        _set_feedback(
            "success",
            f"Saved attendance for {save_result['changed_count']} cadet(s).",
        )
    st.rerun()

st.subheader("Recent Changes")


@st.fragment
def _render_recent_changes() -> None:
    history_page = int(st.session_state.get("_attendance_history_page", 1) or 1)
    history = get_event_change_history(
        event_id,
        page=history_page,
        page_size=HISTORY_PAGE_SIZE,
    )

    if not history["items"]:
        st.caption("No saved attendance changes yet for this event.")
        return

    with st.container(border=True):
        st.caption("Most recent attendance edits for the selected event.")
        selected_change_id = st.session_state.get("_attendance_selected_change_id")
        selection = st.dataframe(
            build_recent_changes_table(history["items"]),
            hide_index=True,
            width="stretch",
            column_config={
                "Timestamp": st.column_config.TextColumn(disabled=True),
                "Cadet": st.column_config.TextColumn(disabled=True),
                "From": st.column_config.TextColumn(disabled=True),
                "To": st.column_config.TextColumn(disabled=True),
                "Changed By": st.column_config.TextColumn(disabled=True),
                "Action": st.column_config.TextColumn(disabled=True),
                "Available": st.column_config.TextColumn(disabled=True),
            },
            key=_recent_changes_table_key(),
            on_select="rerun",
            selection_mode="single-row",
        )

        previous_selected_change_id = st.session_state.get(
            "_attendance_selected_change_id"
        )
        st.session_state["_attendance_selected_change_id"] = get_selected_change_id(
            selection,
            history["items"],
        )

        selected_change_id = st.session_state.get("_attendance_selected_change_id")
        if selected_change_id != previous_selected_change_id:
            _clear_recent_changes_feedback()

        selected_item = get_selected_change_item(
            selected_change_id,
            history["items"],
        )

        st.divider()
        _show_recent_changes_feedback()

        if selected_item is not None:
            st.caption(
                f"Selected change: {selected_item['cadet_name']} • "
                f"{selected_item['from_status']} -> {selected_item['to_status']}"
            )

            if selected_item["can_undo"]:
                st.warning(
                    f"Undo this change for {selected_item['cadet_name']}? This will restore "
                    f"{selected_item['undo_target_label']}."
                )
                if st.button(
                    "Confirm Undo",
                    key=f"confirm_undo_{selected_item['change_id']}",
                    type="primary",
                ):
                    ok, message = undo_change(
                        selected_item["change_id"],
                        recorded_by_user_id=user["_id"],
                        recorded_by_roles=list(user.get("roles", [])),
                    )
                    if ok:
                        st.session_state["_attendance_history_page"] = 1
                        _reset_recent_changes_selection()
                    _set_recent_changes_feedback(
                        "success" if ok else "error",
                        message,
                    )
                    st.rerun()
            elif selected_item["can_redo"]:
                st.warning(
                    f"Redo this change for {selected_item['cadet_name']}? This will restore "
                    f"{selected_item['redo_target_label']}."
                )
                if st.button(
                    "Confirm Redo",
                    key=f"confirm_redo_{selected_item['change_id']}",
                    type="primary",
                ):
                    ok, message = redo_change(
                        selected_item["change_id"],
                        recorded_by_user_id=user["_id"],
                        recorded_by_roles=list(user.get("roles", [])),
                    )
                    if ok:
                        st.session_state["_attendance_history_page"] = 1
                        _reset_recent_changes_selection()
                    _set_recent_changes_feedback(
                        "success" if ok else "error",
                        message,
                    )
                    st.rerun()
            elif selected_item["action_block_reason"]:
                st.caption(selected_item["action_block_reason"])

        st.divider()
        page_col, prev_col, next_col = st.columns([3, 1, 1])
        page_col.caption(
            f"Page {history['page']} of {history['total_pages']}"
            f" • {history['total_count']} total change(s)"
        )
        if prev_col.button(
            "Previous",
            key="attendance_history_prev",
            disabled=history["page"] <= 1,
            width="stretch",
        ):
            st.session_state["_attendance_history_page"] = history["page"] - 1
            _reset_recent_changes_selection()
            _clear_recent_changes_feedback()
            st.rerun(scope="fragment")
        if next_col.button(
            "Next",
            key="attendance_history_next",
            disabled=history["page"] >= history["total_pages"],
            width="stretch",
        ):
            st.session_state["_attendance_history_page"] = history["page"] + 1
            _reset_recent_changes_selection()
            _clear_recent_changes_feedback()
            st.rerun(scope="fragment")


_render_recent_changes()
