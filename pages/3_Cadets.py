import time

import pandas as pd
import streamlit as st
from utils.auth import require_role
from utils.db_schema_crud import (
    update_cadet,
    delete_cadet,
)

from services.cadets import add_cadet_for_user, get_all_cadets, validate_cadet_input


require_role("admin", "cadre")

RANK_OPTIONS = (
    "100/150 (freshman)",
    "200/250/500 (sophomore)",
    "300 (junior)",
    "400 (senior)",
    "700/800/900 (super senior)",
)


def add_cadet():
    if st.session_state.show_form:
        with st.form("add_cadet"):
            cadet_name = st.text_input("Name")
            cadet_lastname = st.text_input("Last Name")
            cadet_email = st.text_input("Email (must match an existing user account)")
            cadet_rank = st.selectbox("Rank", RANK_OPTIONS)

            col1, col2, spacer = st.columns([2, 2, 10])
            with col1:
                submit_button = st.form_submit_button("Submit")
            with col2:
                cancel_button = st.form_submit_button("Cancel", type="secondary")

        if cancel_button:
            st.session_state.show_form = False
            st.rerun()

        if submit_button:
            check, msg = validate_cadet_input(cadet_name, cadet_lastname, cadet_email)
            if check:
                if add_cadet_for_user(
                    cadet_email, cadet_rank, cadet_name, cadet_lastname
                ):
                    st.session_state.show_form = False
                    st.session_state.success_msg = "New cadet added successfully!"
                    st.session_state.success_time = time.time()
                    st.rerun()
                else:
                    st.error("User not found!")
            else:
                st.error(msg)
    else:
        if st.session_state.success_time:
            if time.time() - st.session_state.success_time < 3:
                st.success(st.session_state.success_msg)
                time.sleep(1)
                st.rerun()
            else:
                st.session_state.success_time = None
                st.session_state.success_msg = None


def edit_cadet(cadet):
    current_rank = cadet.get("rank", "")
    rank_index = RANK_OPTIONS.index(current_rank) if current_rank in RANK_OPTIONS else 0
    cadet_id = str(cadet["_id"])

    new_first = st.text_input(
        "First Name", cadet.get("first_name", ""), key=f"first_{cadet_id}"
    )
    new_last = st.text_input(
        "Last Name", cadet.get("last_name", ""), key=f"last_{cadet_id}"
    )
    new_email = st.text_input("Email", cadet.get("email", ""), key=f"email_{cadet_id}")
    new_rank = st.selectbox(
        "Rank", RANK_OPTIONS, index=rank_index, key=f"rank_{cadet_id}"
    )

    col1, col2, spacer = st.columns([2, 2, 10])
    if col1.button("Save", key=f"save_{cadet_id}"):
        check, msg = validate_cadet_input(new_first, new_last, new_email)
        if check:
            update_cadet(
                cadet_id,
                {
                    "first_name": new_first,
                    "last_name": new_last,
                    "email": new_email,
                    "rank": new_rank,
                },
            )
            st.session_state.editing_id = None
            st.rerun()
        else:
            st.error(msg)

    if col2.button("Cancel", key=f"cancel_{cadet_id}"):
        st.session_state.editing_id = None
        st.rerun()


def remove_cadet(cadet):
    cadet_id = str(cadet["_id"])
    st.warning(
        f"Are you sure you want to delete {cadet.get('first_name', '')} {cadet.get('last_name', '')}?"
    )
    col1, col2, spacer = st.columns([2, 2, 10])

    if col1.button("Yes", key=f"confirm_{cadet_id}"):
        result = delete_cadet(cadet_id)
        if result and result.deleted_count > 0:
            st.session_state.confirm_delete_id = None
            st.session_state.success_msg = "Cadet deleted successfully!"
            st.session_state.success_time = time.time()
            st.rerun()
        else:
            st.error("Failed to delete cadet.")

    if col2.button("Cancel", key=f"canceldelete_{cadet_id}"):
        st.session_state.confirm_delete_id = None
        st.rerun()


def show_cadets():
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None
    if "selected_cadet_id" not in st.session_state:
        st.session_state.selected_cadet_id = None

    cadets = get_all_cadets()
    if not cadets:
        st.warning("No cadets found.")
        return

    if st.session_state.success_time:
        if time.time() - st.session_state.success_time < 3:
            st.success(st.session_state.success_msg)
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.success_time = None
            st.session_state.success_msg = None

    st.subheader(f"Total Number of Cadets: {len(cadets)}")

    rows: list[dict[str, str | int]] = []
    cadet_by_id: dict[str, dict] = {}
    for i, cadet in enumerate(cadets):
        cid = str(cadet.get("_id"))
        cadet_by_id[cid] = cadet
        rows.append(
            {
                "No.": i + 1,
                "First Name": str(cadet.get("first_name", "") or ""),
                "Last Name": str(cadet.get("last_name", "") or ""),
                "Email": str(cadet.get("email", "") or ""),
                "Rank": str(cadet.get("rank", "") or ""),
            }
        )

    df = pd.DataFrame(
        rows,
        columns=pd.Index(["No.", "First Name", "Last Name", "Email", "Rank"]),
    )
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()

    def _cadet_label(cadet_id: str) -> str:
        c = cadet_by_id.get(cadet_id, {})
        first = str(c.get("first_name", "") or "").strip()
        last = str(c.get("last_name", "") or "").strip()
        email = str(c.get("email", "") or "").strip()
        name = f"{first} {last}".strip() or "Unknown"
        return f"{name} ({email})".strip()

    cadet_ids = list(cadet_by_id.keys())
    if not cadet_ids:
        return

    # Keep selection stable across reruns.
    if st.session_state.selected_cadet_id not in cadet_by_id:
        st.session_state.selected_cadet_id = cadet_ids[0]

    selected_id = st.selectbox(
        "Select cadet",
        options=cadet_ids,
        format_func=_cadet_label,
        key="selected_cadet_id",
    )

    action_col1, action_col2, _ = st.columns([2, 2, 10])
    with action_col1:
        if st.button("Edit", key="edit_selected_cadet"):
            st.session_state.editing_id = str(selected_id)
            st.session_state.confirm_delete_id = None
            st.rerun()
    with action_col2:
        if st.button("Delete", key="delete_selected_cadet"):
            st.session_state.confirm_delete_id = str(selected_id)
            st.session_state.editing_id = None
            st.rerun()

    if st.session_state.editing_id in cadet_by_id:
        st.divider()
        edit_cadet(cadet_by_id[st.session_state.editing_id])

    if st.session_state.confirm_delete_id in cadet_by_id:
        st.divider()
        remove_cadet(cadet_by_id[st.session_state.confirm_delete_id])


st.title("Cadet Management")

try:
    get_all_cadets()
    st.success("Database connection established successfully!")
except Exception:
    st.warning("Database is not configured as of now.")
    st.stop()

if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "success_time" not in st.session_state:
    st.session_state.success_time = None
if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

if st.button("Add Cadet"):
    st.session_state.show_form = True
if st.session_state.show_form or st.session_state.success_time:
    add_cadet()

show_cadets()
