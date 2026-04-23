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
from services.commander_attendance import (
    get_paginated_commander_roster,
    get_roster_entries_for_cadet_ids,
)
from services.events import closest_event_index, get_all_events, has_event_ended
from utils.auth import get_current_user, require_role
from utils.st_helpers import require
from utils.attendance_status import (
    NO_RECORD_STATUS_LABEL,
    get_attendance_status_cell_style,
    get_attendance_status_label,
)
from utils.pagination import init_pagination_state, render_pagination_controls, sync_pagination_state
from utils.db_schema_crud import (
    get_user_by_email,
)

STATUS_OPTIONS = [NO_RECORD_STATUS_LABEL, "Present", "Absent", "Excused"]
STATUS_TO_DB = {"Present": "present", "Absent": "absent", "Excused": "excused"}

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
    st.session_state["_attendance_selected_change_id"] = None
    st.session_state["_attendance_recent_changes_table_version"] = 0
    st.session_state["_attendance_recent_changes_feedback"] = None


def _sync_roster_state(event_id: str) -> None:
    previous_event_id = st.session_state.get("_attendance_roster_event_id")
    if previous_event_id == event_id:
        return

    st.session_state["_attendance_roster_event_id"] = event_id
    st.session_state["_attendance_roster_drafts"] = {}


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


def _sync_roster_drafts(
    edited: pd.DataFrame,
    roster: list[dict[str, Any]],
    *,
    default_status: str,
) -> None:
    drafts = dict(st.session_state.get("_attendance_roster_drafts", {}))
    for idx, (_, row) in enumerate(edited.iterrows()):
        cadet_id = str(roster[idx]["cadet"]["_id"])
        current_label = get_attendance_status_label(
            roster[idx]["current_status"],
            default=default_status,
        )
        selected_label = str(row["Set Status"])
        if selected_label == current_label:
            drafts.pop(cadet_id, None)
        else:
            drafts[cadet_id] = selected_label

    st.session_state["_attendance_roster_drafts"] = drafts


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
_sync_roster_state(str(event_id))

st.subheader("Attendance Roster")

@st.fragment
def _render_attendance_roster() -> None:
    roster_page, roster_page_size = init_pagination_state(
        "attendance_roster",
        reset_token=str(event_id),
    )
    roster_page_data = get_paginated_commander_roster(
        event_id,
        page=roster_page,
        page_size=roster_page_size,
    )
    sync_pagination_state("attendance_roster", roster_page_data)

    roster = list(roster_page_data["items"])
    if not roster:
        st.info("No cadets found.")
        return

    draft_statuses = dict(st.session_state.get("_attendance_roster_drafts", {}))
    current_statuses = [
        get_attendance_status_label(entry["current_status"], default=default_status)
        for entry in roster
    ]
    selected_statuses = [
        draft_statuses.get(str(entry["cadet"]["_id"]), current_statuses[idx])
        for idx, entry in enumerate(roster)
    ]

    df = pd.DataFrame(
        {
            "Cadet": [
                str(entry["cadet"].get("name", "") or "").strip()
                or f"{str(entry['cadet'].get('last_name', '') or '').strip()}, "
                f"{str(entry['cadet'].get('first_name', '') or '').strip()}".strip(", ")
                or "Unknown"
                for entry in roster
            ],
            "Current Status": current_statuses,
            "Set Status": selected_statuses,
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
                options=STATUS_OPTIONS,
                required=True,
            ),
        },
        hide_index=True,
        width="stretch",
        key=(
            f"attendance_roster_editor_"
            f"{event_id}_{roster_page_data['page']}_{roster_page_data['page_size']}"
        ),
    )
    _sync_roster_drafts(edited, roster, default_status=default_status)

    render_pagination_controls(
        "attendance_roster",
        roster_page_data,
        rerun_scope="fragment",
    )

    st.divider()
    if st.button("Save All", type="primary", key="attendance_roster_save_all"):
        _sync_roster_drafts(edited, roster, default_status=default_status)
        drafts = dict(st.session_state.get("_attendance_roster_drafts", {}))
        if not drafts:
            _set_feedback("info", "No attendance changes to save.")
            st.rerun()

        draft_cadet_ids = list(drafts.keys())
        roster_to_save = get_roster_entries_for_cadet_ids(event_id, draft_cadet_ids)
        if not roster_to_save:
            _set_feedback("error", "Could not load attendance roster for the selected edits.")
            st.rerun()

        invalid_no_record_rows = [
            entry["cadet"]
            for entry in roster_to_save
            if drafts.get(str(entry["cadet"]["_id"])) == NO_RECORD_STATUS_LABEL
            and entry["record"] is not None
        ]
        if invalid_no_record_rows:
            st.error(
                "No Record can only be used for cadets who do not already have an attendance entry."
            )
            st.stop()

        new_statuses = {
            str(entry["cadet"]["_id"]): STATUS_TO_DB[
                drafts[str(entry["cadet"]["_id"])]
            ]
            for entry in roster_to_save
            if drafts.get(str(entry["cadet"]["_id"])) in STATUS_TO_DB
        }
        save_result = apply_bulk_attendance_changes(
            event_id=event_id,
            roster=roster_to_save,
            new_statuses=new_statuses,
            recorded_by_user_id=user["_id"],
            recorded_by_roles=list(user.get("roles", [])),
        )
        if save_result["changed_count"] == 0:
            _set_feedback("info", "No attendance changes to save.")
        else:
            st.session_state["_attendance_roster_drafts"] = {}
            st.session_state["attendance_history_page"] = 1
            _reset_recent_changes_selection()
            _clear_recent_changes_feedback()
            _set_feedback(
                "success",
                f"Saved attendance for {save_result['changed_count']} cadet(s).",
            )
        st.rerun()


_render_attendance_roster()

st.subheader("Recent Changes")


@st.fragment
def _render_recent_changes() -> None:
    history_page, history_page_size = init_pagination_state(
        "attendance_history",
        reset_token=str(event_id),
    )
    history = get_event_change_history(
        event_id,
        page=history_page,
        page_size=history_page_size,
    )
    sync_pagination_state("attendance_history", history)

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
                        st.session_state["attendance_history_page"] = 1
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
                        st.session_state["attendance_history_page"] = 1
                        _reset_recent_changes_selection()
                    _set_recent_changes_feedback(
                        "success" if ok else "error",
                        message,
                    )
                    st.rerun()
            elif selected_item["action_block_reason"]:
                st.caption(selected_item["action_block_reason"])

        st.divider()
        render_pagination_controls(
            "attendance_history",
            history,
            rerun_scope="fragment",
        )


_render_recent_changes()
