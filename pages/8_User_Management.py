from __future__ import annotations

from typing import Any

import streamlit as st

from utils.auth import require_role
from utils.db import get_collection
from utils.db_schema_crud import create_user, update_user, delete_user
from utils.admin_users import (
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


def _get_existing_emails(exclude_user_id: Any | None = None) -> set[str]:
    users = _load_users()
    emails: set[str] = set()
    for u in users:
        if exclude_user_id is not None and u.get("_id") == exclude_user_id:
            continue
        email = str(u.get("email", "") or "").strip()
        if email:
            emails.add(email)
    return emails


def _render_display_row(summary: dict[str, str]) -> None:
    cols = st.columns([3, 4, 2, 3])
    cols[0].write(summary["name"])
    cols[1].write(summary["email"])
    cols[2].write(summary["role"] or "-")

    edit_btn, delete_btn = cols[3].columns(2)
    if edit_btn.button("Edit", key=f"edit_{summary['id']}"):
        st.session_state["admin_users_editing"] = summary["id"]
        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()
    if delete_btn.button("Delete", key=f"delete_{summary['id']}"):
        st.session_state["admin_users_confirm_delete"] = summary["id"]
        st.session_state["admin_users_editing"] = None
        st.rerun()


def _render_edit_row(summary: dict[str, str]) -> None:
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
        # Find the full existing user document by id
        existing_user = next(
            (u for u in _load_users() if str(u.get("_id")) == user_id), None
        )
        if existing_user is None:
            st.error("User no longer exists.")
            st.session_state["admin_users_editing"] = None
            st.rerun()
            return

        other_emails = _get_existing_emails(exclude_user_id=existing_user["_id"])
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
                st.success("User updated successfully.")
                st.session_state["admin_users_editing"] = None
                st.rerun()
            else:
                st.error("Failed to update user (database unavailable).")

    if cancel_btn.button("Cancel", key=f"cancel_{user_id}"):
        st.session_state["admin_users_editing"] = None
        st.rerun()


def _render_delete_confirmation(summary: dict[str, str]) -> None:
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

        # Fetch the latest user doc and delete it
        existing_user = next(
            (u for u in _load_users() if str(u.get("_id")) == summary["id"]), None
        )
        if existing_user is None:
            st.error("User no longer exists.")
        else:
            result = delete_user(existing_user["_id"])
            if result is not None:
                st.success("User deleted successfully.")
            else:
                st.error("Failed to delete user (database unavailable).")

        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()

    if cancel_btn.button("Cancel", key=f"cancel_delete_{summary['id']}"):
        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()


require_role("admin")
st.title("User Management")
st.caption("Create, edit, and delete user accounts and roles.")


# ----------------------------
# Create New User
# ----------------------------

st.subheader("Create New User")
with st.form("create_user_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name")
        email = st.text_input("Email")
    with col2:
        last_name = st.text_input("Last Name")
        role = st.selectbox("Role", sorted(ALLOWED_ROLES))

    password = st.text_input("Temporary Password", type="password")
    create_submitted = st.form_submit_button("Create User")

    if create_submitted:
        existing_emails = _get_existing_emails()
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
            # create_user expects first_name, last_name, email, password, roles
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

st.subheader("Existing Users")

raw_users = _load_users()
if not raw_users:
    st.info("No users found in the system.")
else:
    summaries = list_users_for_admin(raw_users)

    if "admin_users_editing" not in st.session_state:
        st.session_state["admin_users_editing"] = None
    if "admin_users_confirm_delete" not in st.session_state:
        st.session_state["admin_users_confirm_delete"] = None

    # Simple table-style header
    header_cols = st.columns([3, 4, 2, 3])
    header_cols[0].markdown("**Name**")
    header_cols[1].markdown("**Email**")
    header_cols[2].markdown("**Role**")
    header_cols[3].markdown("**Actions**")
    st.divider()

    for summary in summaries:
        user_id = summary["id"]
        is_editing = st.session_state["admin_users_editing"] == user_id
        is_confirming_delete = st.session_state["admin_users_confirm_delete"] == user_id

        if is_editing:
            _render_edit_row(summary)
        else:
            _render_display_row(summary)

        if is_confirming_delete:
            _render_delete_confirmation(summary)

        st.divider()
