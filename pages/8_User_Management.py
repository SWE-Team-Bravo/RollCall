from __future__ import annotations

from typing import Any

import streamlit as st
import pandas as pd

from utils.auth import require_role
from utils.db import get_collection
from utils.db_schema_crud import create_user, update_user, delete_user
from services.admin_users import (
    list_users_for_admin,
    validate_new_user_data,
    build_update_user_payload,
    confirm_delete_user,
    ALLOWED_ROLES,
)


def _load_users() -> list[dict[str, Any]]:
    col = get_collection("users")
    if col is None:
        return []
    return list(col.find())


def _get_existing_emails(
    users: list[dict[str, Any]], exclude_user_id: Any | None = None
) -> set[str]:
    emails: set[str] = set()
    for u in users:
        if exclude_user_id is not None and u.get("_id") == exclude_user_id:
            continue
        email = str(u.get("email", "") or "").strip()
        if email:
            emails.add(email)
    return emails


def _render_edit_row(summary: dict[str, str], users: list[dict[str, Any]]) -> None:
    cols = st.columns([3, 4, 2, 3])

    user_id = summary["id"]

    new_first = cols[0].text_input(
        "First Name",
        summary["name"].split(" ", 1)[0] if " " in summary["name"] else summary["name"],
        key=f"edit_first_{user_id}",
    )
    new_last = cols[0].text_input(
        "Last Name",
        summary["name"].split(" ", 1)[1] if " " in summary["name"] else "",
        key=f"edit_last_{user_id}",
    )
    new_email = cols[1].text_input(
        "Email",
        summary["email"],
        key=f"edit_email_{user_id}",
    )
    new_role = cols[2].selectbox(
        "Role",
        options=sorted(ALLOWED_ROLES),
        index=sorted(ALLOWED_ROLES).index(summary["role"])
        if summary["role"] in ALLOWED_ROLES
        else 0,
        key=f"edit_role_{user_id}",
    )

    save_btn, cancel_btn = cols[3].columns(2)

    if save_btn.button("Save", key=f"save_{user_id}"):
        # Find the full existing user document by id from the provided list
        existing_user = next((u for u in users if str(u.get("_id")) == user_id), None)
        if existing_user is None:
            st.error("User no longer exists.")
            st.session_state["admin_users_editing"] = None
            st.rerun()
            return

        other_emails = _get_existing_emails(users, exclude_user_id=existing_user["_id"])
        updates, errors = build_update_user_payload(
            existing_user=existing_user,
            new_first_name=new_first,
            new_last_name=new_last,
            new_email=new_email,
            new_role=new_role,
            other_emails=other_emails,
        )

        if errors:
            for field, msg in errors.items():
                st.error(f"{field.capitalize()}: {msg}")
        else:
            result = update_user(existing_user["_id"], updates)
            if result is not None:
                st.session_state["_success_msg"] = "User updated successfully."
                st.session_state["admin_users_editing"] = None
                st.rerun()
            else:
                st.error("Failed to update user (database unavailable).")

    if cancel_btn.button("Cancel", key=f"cancel_{user_id}", type="secondary"):
        st.session_state["admin_users_editing"] = None
        st.rerun()


def _render_delete_confirmation(
    summary: dict[str, str], users: list[dict[str, Any]]
) -> None:
    st.warning(
        f"Type DELETE below to permanently delete user {summary['email']}.",
    )
    confirmation = st.text_input(
        "Confirm delete",
        key=f"confirm_input_{summary['id']}",
    )
    confirm_btn, cancel_btn = st.columns(2)

    if confirm_btn.button("Confirm Delete", key=f"confirm_btn_{summary['id']}"):
        if not confirm_delete_user(confirmation):
            st.error("Confirmation text does not match 'DELETE'.")
            return

        # Fetch the latest user doc and delete it from the provided list
        existing_user = next(
            (u for u in users if str(u.get("_id")) == summary["id"]), None
        )
        if existing_user is None:
            st.error("User no longer exists.")
        else:
            result = delete_user(existing_user["_id"])
            if result is not None:
                st.session_state["_success_msg"] = "User deleted successfully."
            else:
                st.error("Failed to delete user (database unavailable).")

        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()

    if cancel_btn.button("Cancel", key=f"cancel_delete_{summary['id']}", type="secondary"):
        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()


require_role("admin")
st.title("User Management")
st.caption("Create, edit, and delete user accounts and roles.")

if "_success_msg" not in st.session_state:
    st.session_state["_success_msg"] = None
if st.session_state["_success_msg"]:
    st.success(st.session_state["_success_msg"])
    st.session_state["_success_msg"] = None


# ----------------------------
# Create New User
# ----------------------------

with st.expander("Create New User", expanded=False):
    with st.form("create_user_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name")
            email = st.text_input("Email")
        with col2:
            last_name = st.text_input("Last Name")
            role = st.selectbox("Role", sorted(ALLOWED_ROLES))

        password = st.text_input("Temporary Password", type="password")
        create_submitted = st.form_submit_button("Create User", type="primary")

    if create_submitted:
        # Load current users for email-uniqueness validation.
        existing_emails = _get_existing_emails(_load_users())
        payload, errors = validate_new_user_data(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            role=role,
            existing_emails=existing_emails,
        )

        if errors:
            for field, msg in errors.items():
                st.error(f"{field.capitalize()}: {msg}")
        else:
            result = create_user(
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                email=payload["email"],
                password=payload["password"],
                roles=payload["roles"],
            )
            if result is not None:
                st.success("User created successfully.")
            else:
                st.error("Failed to create user (database unavailable).")


# ----------------------------
# Existing Users
# ----------------------------

# Load users once per rerun to avoid repeated collection scans.
raw_users: list[dict[str, Any]] = _load_users()

st.subheader("Existing Users")
if not raw_users:
    st.info("No users found in the system.")
else:
    summaries = list_users_for_admin(raw_users)
    summary_by_id: dict[str, dict[str, str]] = {s["id"]: s for s in summaries}

    if "admin_users_editing" not in st.session_state:
        st.session_state["admin_users_editing"] = None
    if "admin_users_confirm_delete" not in st.session_state:
        st.session_state["admin_users_confirm_delete"] = None
    if "admin_users_selected" not in st.session_state:
        st.session_state["admin_users_selected"] = (
            summaries[0]["id"] if summaries else None
        )

    st.subheader("Filters")
    f1, f2 = st.columns([2, 4])
    with f1:
        role_filter = st.selectbox(
            "Role",
            options=["All"] + sorted(ALLOWED_ROLES),
            index=0,
        )
    with f2:
        search = st.text_input("Search (name or email)", value="")

    search_norm = search.strip().lower()
    filtered = []
    for s in summaries:
        role = str(s.get("role", "") or "")
        if role_filter != "All" and role != role_filter:
            continue
        if search_norm:
            hay = f"{s.get('name', '')} {s.get('email', '')}".lower()
            if search_norm not in hay:
                continue
        filtered.append(s)

    if not filtered:
        st.info("No users match your filters.")
    else:
        df = pd.DataFrame(
            [
                {
                    "Name": s.get("name", ""),
                    "Email": s.get("email", ""),
                    "Role": s.get("role", "") or "-",
                }
                for s in filtered
            ],
            columns=pd.Index(["Name", "Email", "Role"]),
        )
        st.dataframe(df, hide_index=True, width="stretch")

        filtered_ids = [s["id"] for s in filtered]
        if st.session_state.admin_users_selected not in filtered_ids:
            st.session_state.admin_users_selected = filtered_ids[0]

        def _label(user_id: str) -> str:
            s = summary_by_id.get(user_id, {})
            name = str(s.get("name", "") or "").strip() or "User"
            email = str(s.get("email", "") or "").strip()
            return f"{name} ({email})".strip()

        selected_id = st.selectbox(
            "Select user",
            options=filtered_ids,
            format_func=_label,
            key="admin_users_selected",
        )

        b1, b2, _ = st.columns([2, 2, 10])
        with b1:
            if st.button("Edit", key="admin_users_edit_selected"):
                st.session_state["admin_users_editing"] = selected_id
                st.session_state["admin_users_confirm_delete"] = None
                st.rerun()
        with b2:
            if st.button("Delete", key="admin_users_delete_selected"):
                st.session_state["admin_users_confirm_delete"] = selected_id
                st.session_state["admin_users_editing"] = None
                st.rerun()

    editing_id = st.session_state.get("admin_users_editing")
    confirm_id = st.session_state.get("admin_users_confirm_delete")

    if editing_id and editing_id in summary_by_id:
        st.divider()
        _render_edit_row(summary_by_id[editing_id], raw_users)

    if confirm_id and confirm_id in summary_by_id:
        st.divider()
        _render_delete_confirmation(summary_by_id[confirm_id], raw_users)
