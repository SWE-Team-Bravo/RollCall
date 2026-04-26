from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st
import pandas as pd

from utils.audit_log import log_data_change, serialize_doc_for_audit
from utils.auth import get_current_user_doc, require_role
from utils.db import get_collection
from utils.db_schema_crud import create_user, update_user, delete_user
from utils.password_reset import build_password_updates
from utils.password_reset_email import send_temporary_password_email
from services.admin_users import (
    confirm_destructive_action,
    list_users_for_admin,
    validate_new_user_data,
    build_update_user_payload,
    validate_disable_user,
    is_user_disabled,
    ALLOWED_ROLES,
)
from utils.pagination import (
    init_pagination_state,
    paginate_list,
    render_pagination_controls,
    sync_pagination_state,
)


require_role("admin")


def _load_users() -> list[dict[str, Any]]:
    col = get_collection("users")
    if col is None:
        return []
    return list(col.find())


def _load_user_by_id(user_id: Any) -> dict[str, Any] | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.find_one({"_id": user_id})


def _audit_user_change(
    *,
    action: str,
    target_label: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor_user: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    target = after or before or {}
    target_id = target.get("_id")
    if target_id is None:
        return

    log_data_change(
        source="user_management",
        action=action,
        target_collection="users",
        target_id=target_id,
        actor_user_id=actor_user.get("_id") if actor_user else None,
        actor_email=str(actor_user.get("email", "") or "").strip() or None
        if actor_user
        else None,
        actor_roles=list(actor_user.get("roles", [])) if actor_user else [],
        target_label=target_label,
        before=serialize_doc_for_audit(before),
        after=serialize_doc_for_audit(after),
        metadata=metadata,
    )


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


def _render_edit_row(
    summary: dict[str, Any],
    users: list[dict[str, Any]],
    actor_user: dict[str, Any] | None,
) -> None:
    cols = st.columns([3, 4, 2, 3])

    user_id = summary["id"]
    existing_user = next((u for u in users if str(u.get("_id")) == user_id), None)
    if existing_user is None:
        st.error("User no longer exists.")
        st.session_state["admin_users_editing"] = None
        st.rerun()
    assert existing_user is not None

    new_first = cols[0].text_input(
        "First Name",
        str(existing_user.get("first_name", "") or ""),
        key=f"edit_first_{user_id}",
    )
    new_last = cols[0].text_input(
        "Last Name",
        str(existing_user.get("last_name", "") or ""),
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
    new_waiver_reviewer = cols[2].checkbox(
        "Waiver reviewer",
        value=bool(summary.get("waiver_reviewer", False)),
        key=f"edit_wr_{user_id}",
    )

    save_btn, cancel_btn = cols[3].columns(2)

    if save_btn.button("Save", key=f"save_{user_id}"):
        other_emails = _get_existing_emails(users, exclude_user_id=existing_user["_id"])
        updates, errors = build_update_user_payload(
            existing_user=existing_user,
            new_first_name=new_first,
            new_last_name=new_last,
            new_email=new_email,
            new_role=new_role,
            other_emails=other_emails,
            waiver_reviewer=new_waiver_reviewer,
        )

        if errors:
            for field, msg in errors.items():
                st.error(f"{field.capitalize()}: {msg}")
        else:
            before_user = dict(existing_user)
            result = update_user(existing_user["_id"], updates)
            if result is not None:
                after_user = _load_user_by_id(existing_user["_id"])
                _audit_user_change(
                    action="update",
                    target_label=str(existing_user.get("email", "") or "User"),
                    before=before_user,
                    after=after_user,
                    actor_user=actor_user,
                )
                st.success("User updated successfully.")
                st.session_state["admin_users_editing"] = None
                st.rerun()
            else:
                st.error("Failed to update user (database unavailable).")

    if cancel_btn.button("Cancel", key=f"cancel_{user_id}"):
        st.session_state["admin_users_editing"] = None
        st.rerun()


actor_user = get_current_user_doc()


def _render_status_confirmation(
    summary: dict[str, Any],
    users: list[dict[str, Any]],
    actor_user: dict[str, Any] | None,
) -> None:
    existing_user = next((u for u in users if str(u.get("_id")) == summary["id"]), None)
    if existing_user is None:
        st.error("User no longer exists.")
        st.session_state["admin_users_confirm_status_change"] = None
        return

    if is_user_disabled(existing_user):
        st.warning(f"Enable user {summary['email']}?")
        confirm_btn, cancel_btn = st.columns(2)
        if confirm_btn.button("Enable User", key=f"confirm_enable_{summary['id']}"):
            before_user = dict(existing_user)
            result = update_user(
                existing_user["_id"],
                {
                    "disabled": False,
                    "disabled_at": None,
                    "disabled_by_user_id": None,
                    "disabled_reason": None,
                },
            )
            if result is not None:
                after_user = _load_user_by_id(existing_user["_id"])
                _audit_user_change(
                    action="enable",
                    target_label=str(existing_user.get("email", "") or "User"),
                    before=before_user,
                    after=after_user,
                    actor_user=actor_user,
                )
                st.session_state["admin_users_success"] = "User enabled successfully."
            else:
                st.error("Failed to enable user (database unavailable).")

            st.session_state["admin_users_confirm_status_change"] = None
            st.rerun()

        if cancel_btn.button("Cancel", key=f"cancel_enable_{summary['id']}"):
            st.session_state["admin_users_confirm_status_change"] = None
            st.rerun()
        return

    st.warning(
        f"Type DELETE below to disable user {summary['email']} without removing their history.",
    )
    confirmation = st.text_input(
        "Confirm disable",
        key=f"confirm_input_{summary['id']}",
    )
    confirm_btn, cancel_btn = st.columns(2)

    if confirm_btn.button("Confirm Disable", key=f"confirm_disable_{summary['id']}"):
        if not confirm_destructive_action(confirmation):
            st.error("Confirmation text does not match 'DELETE'.")
            return

        error = validate_disable_user(existing_user, actor_user, users)
        if error:
            st.error(error)
            return

        before_user = dict(existing_user)
        updates = {
            "disabled": True,
            "disabled_at": datetime.now(timezone.utc),
            "disabled_by_user_id": actor_user.get("_id") if actor_user else None,
            "disabled_reason": "Disabled by admin",
        }
        result = update_user(existing_user["_id"], updates)
        if result is not None:
            after_user = _load_user_by_id(existing_user["_id"])
            _audit_user_change(
                action="disable",
                target_label=str(existing_user.get("email", "") or "User"),
                before=before_user,
                after=after_user,
                actor_user=actor_user,
            )
            st.session_state["admin_users_success"] = "User disabled successfully."
            st.session_state.pop("admin_users_selected", None)
        else:
            st.error("Failed to disable user (database unavailable).")

        st.session_state["admin_users_confirm_status_change"] = None
        st.rerun()

    if cancel_btn.button("Cancel", key=f"cancel_disable_{summary['id']}"):
        st.session_state["admin_users_confirm_status_change"] = None
        st.rerun()


def _render_delete_confirmation(
    summary: dict[str, Any],
    users: list[dict[str, Any]],
    actor_user: dict[str, Any] | None,
) -> None:
    existing_user = next((u for u in users if str(u.get("_id")) == summary["id"]), None)
    if existing_user is None:
        st.error("User no longer exists.")
        st.session_state["admin_users_confirm_delete"] = None
        return

    st.warning(
        f"Type DELETE below to **permanently delete** user {summary['email']}. "
        "This action cannot be undone.",
    )
    confirmation = st.text_input(
        "Confirm deletion",
        key=f"confirm_delete_input_{summary['id']}",
    )
    confirm_btn, cancel_btn = st.columns(2)

    if confirm_btn.button(
        "Confirm Delete", type="primary", key=f"confirm_delete_{summary['id']}"
    ):
        if not confirm_destructive_action(confirmation):
            st.error("Confirmation text does not match 'DELETE'.")
            return

        before_user = dict(existing_user)
        result = delete_user(existing_user["_id"])
        if result is not None:
            _audit_user_change(
                action="delete",
                target_label=str(existing_user.get("email", "") or "User"),
                before=before_user,
                after=None,
                actor_user=actor_user,
            )
            st.session_state["admin_users_success"] = "User deleted successfully."
            st.session_state.pop("admin_users_selected", None)
        else:
            st.error("Failed to delete user (database unavailable).")

        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()

    if cancel_btn.button("Cancel", key=f"cancel_delete_{summary['id']}"):
        st.session_state["admin_users_confirm_delete"] = None
        st.rerun()


st.title("User Management")
st.caption("Create, edit, disable, and enable user accounts and roles.")
if "admin_users_success" not in st.session_state:
    st.session_state["admin_users_success"] = None

if st.session_state["admin_users_success"]:
    st.success(st.session_state["admin_users_success"])
    st.session_state["admin_users_success"] = None


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
                created_user = _load_user_by_id(result.inserted_id)
                _audit_user_change(
                    action="create",
                    target_label=payload["email"],
                    before=None,
                    after=created_user,
                    actor_user=actor_user,
                )
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
    if "admin_users_confirm_status_change" not in st.session_state:
        st.session_state["admin_users_confirm_status_change"] = None
    if "admin_users_reset_pw" not in st.session_state:
        st.session_state["admin_users_reset_pw"] = None
    if "admin_users_confirm_delete" not in st.session_state:
        st.session_state["admin_users_confirm_delete"] = None
    if "admin_users_last_temp_pw" not in st.session_state:
        st.session_state["admin_users_last_temp_pw"] = None
    if "admin_users_selected" not in st.session_state:
        st.session_state["admin_users_selected"] = (
            summaries[0]["id"] if summaries else None
        )

    st.subheader("Filters")
    f1, f2, f3 = st.columns([2, 2, 4])
    with f1:
        role_filter = st.selectbox(
            "Role",
            options=["All"] + sorted(ALLOWED_ROLES),
            index=0,
        )
    with f2:
        status_filter = st.selectbox(
            "Status",
            options=["All", "Active", "Disabled"],
            index=0,
        )
    with f3:
        search = st.text_input("Search (name or email)", value="")

    search_norm = search.strip().lower()
    filtered = []
    for s in summaries:
        role = str(s.get("role", "") or "")
        if role_filter != "All" and role != role_filter:
            continue
        status = str(s.get("status", "Active") or "Active")
        if status_filter != "All" and status != status_filter:
            continue
        if search_norm:
            hay = f"{s.get('name', '')} {s.get('email', '')}".lower()
            if search_norm not in hay:
                continue
        filtered.append(s)

    if not filtered:
        st.info("No users match your filters.")
    else:
        users_page, users_page_size = init_pagination_state(
            "admin_users",
            reset_token=f"{role_filter}|{status_filter}|{search_norm}",
        )
        paginated_filtered = paginate_list(
            filtered,
            page=users_page,
            page_size=users_page_size,
        )
        sync_pagination_state("admin_users", paginated_filtered)
        page_filtered = list(paginated_filtered["items"])

        df = pd.DataFrame(
            [
                {
                    "Name": s.get("name", ""),
                    "Email": s.get("email", ""),
                    "Role": s.get("role", "") or "-",
                    "Status": s.get("status", "Active"),
                }
                for s in page_filtered
            ],
            columns=pd.Index(["Name", "Email", "Role", "Status"]),
        )
        st.dataframe(df, hide_index=True, width="stretch")
        render_pagination_controls("admin_users", paginated_filtered)

        page_filtered_ids = [s["id"] for s in page_filtered]
        if st.session_state.admin_users_selected not in page_filtered_ids:
            st.session_state.admin_users_selected = page_filtered_ids[0]

        def _label(user_id: str) -> str:
            s = summary_by_id.get(user_id, {})
            name = str(s.get("name", "") or "").strip() or "User"
            email = str(s.get("email", "") or "").strip()
            return f"{name} ({email})".strip()

        selected_id = st.selectbox(
            "Select user",
            options=page_filtered_ids,
            format_func=_label,
            key="admin_users_selected",
        )

        selected_summary = summary_by_id.get(selected_id, {})
        status_action_label = (
            "Enable" if selected_summary.get("disabled") else "Disable"
        )

        b1, b2, b3, b4, _ = st.columns([2, 2, 2, 3, 5])
        with b1:
            if st.button("Edit", key="admin_users_edit_selected"):
                st.session_state["admin_users_editing"] = selected_id
                st.session_state["admin_users_confirm_status_change"] = None
                st.session_state["admin_users_confirm_delete"] = None
                st.session_state["admin_users_reset_pw"] = None
                st.rerun()
        with b2:
            if st.button(status_action_label, key="admin_users_status_selected"):
                st.session_state["admin_users_confirm_status_change"] = selected_id
                st.session_state["admin_users_editing"] = None
                st.session_state["admin_users_confirm_delete"] = None
                st.session_state["admin_users_reset_pw"] = None
                st.rerun()
        with b3:
            if selected_summary.get("disabled") and st.button(
                "Delete User", type="secondary", key="admin_users_delete_selected"
            ):
                st.session_state["admin_users_confirm_delete"] = selected_id
                st.session_state["admin_users_editing"] = None
                st.session_state["admin_users_confirm_status_change"] = None
                st.session_state["admin_users_reset_pw"] = None
                st.rerun()
        with b4:
            if st.button("Reset Password", key="admin_users_reset_selected"):
                st.session_state["admin_users_reset_pw"] = selected_id
                st.session_state["admin_users_editing"] = None
                st.session_state["admin_users_confirm_status_change"] = None
                st.session_state["admin_users_confirm_delete"] = None
                st.session_state["admin_users_last_temp_pw"] = None
                st.rerun()

    editing_id = st.session_state.get("admin_users_editing")
    confirm_id = st.session_state.get("admin_users_confirm_status_change")
    delete_id = st.session_state.get("admin_users_confirm_delete")
    reset_id = st.session_state.get("admin_users_reset_pw")

    if editing_id and editing_id in summary_by_id:
        st.divider()
        _render_edit_row(summary_by_id[editing_id], raw_users, actor_user)

    if confirm_id and confirm_id in summary_by_id:
        st.divider()
        _render_status_confirmation(summary_by_id[confirm_id], raw_users, actor_user)

    if delete_id and delete_id in summary_by_id:
        st.divider()
        _render_delete_confirmation(summary_by_id[delete_id], raw_users, actor_user)

    if reset_id and reset_id in summary_by_id:
        st.divider()
        summary = summary_by_id[reset_id]
        st.subheader("Reset Password")
        st.warning(
            f"This will reset the password for {summary.get('email', '')}.",
        )

        email_user = st.checkbox(
            "Email the temporary password to the user",
            value=True,
            key=f"reset_pw_email_{reset_id}",
        )

        c1, c2, c3 = st.columns([2, 2, 8])
        with c1:
            if st.button(
                "Confirm Reset", type="primary", key=f"reset_pw_confirm_{reset_id}"
            ):
                existing_user = next(
                    (u for u in raw_users if str(u.get("_id")) == reset_id), None
                )
                if existing_user is None:
                    st.error("User no longer exists.")
                else:
                    updates, temp_pw = build_password_updates()
                    before_user = dict(existing_user)
                    result = update_user(existing_user["_id"], updates)
                    if result is None:
                        st.error("Failed to reset password (database unavailable).")
                    else:
                        after_user = _load_user_by_id(existing_user["_id"])
                        _audit_user_change(
                            action="reset_password",
                            target_label=str(existing_user.get("email", "") or "User"),
                            before=before_user,
                            after=after_user,
                            actor_user=actor_user,
                        )
                        st.session_state["admin_users_last_temp_pw"] = temp_pw
                        st.success("Password reset successfully.")

                        if email_user:
                            to_email = str(existing_user.get("email", "") or "").strip()
                            if not to_email:
                                st.warning(
                                    "User has no email address on file; cannot send email."
                                )
                            else:
                                sent = send_temporary_password_email(
                                    to_email=to_email, temporary_password=temp_pw
                                )
                                if sent:
                                    st.success("Temporary password emailed to user.")
                                else:
                                    st.warning(
                                        "Email not sent. If you expect email to work, set EMAIL_ADDRESS and EMAIL_APP_PASSWORD and restart Streamlit."
                                    )

        with c2:
            if st.button("Cancel", key=f"reset_pw_cancel_{reset_id}"):
                st.session_state["admin_users_reset_pw"] = None
                st.session_state["admin_users_last_temp_pw"] = None
                st.rerun()

        last_pw = st.session_state.get("admin_users_last_temp_pw")
        if last_pw:
            st.info("Temporary password (shown once):")
            st.code(last_pw)
