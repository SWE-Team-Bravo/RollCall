import logging

import streamlit as st
from typing import Any, cast

from services.account_settings import (
    build_password_change_updates,
    build_profile_updates,
)
from utils.auth import require_auth, get_current_user
from utils.db_schema_crud import get_user_by_email, update_user
from utils.password import verify_password
from utils.waiver_email import send_test_email

require_auth()

st.title("Account Settings")

user = get_current_user()
if user is None:
    st.error("Could not determine the currently logged-in user.")
    st.stop()

assert user is not None

if "admin" in (user.get("roles") or []):
    if st.button("Send Test Email"):
        ok, error = send_test_email(user["email"])
        if ok:
            st.success("Test email sent successfully.")
        else:
            st.error(f"Failed: {error}")

user = cast(dict[str, Any], user)
email_value = user.get("email")
if not isinstance(email_value, str) or not email_value:
    st.error("Could not determine the currently logged-in user.")
    st.stop()

email = cast(str, email_value)

first_name = str(user.get("first_name", "") or "")
last_name = str(user.get("last_name", "") or "")

st.caption(f"Signed in as **{first_name} {last_name}** ({email})")

user_doc = get_user_by_email(email)
if user_doc is None:
    st.error("Could not load your account from the database.")
    st.stop()

user_doc = cast(dict[str, Any], user_doc)

st.subheader("Update Profile")
with st.form("update_profile_form"):
    new_first_name = st.text_input("First Name", value=first_name)
    new_last_name = st.text_input("Last Name", value=last_name)
    new_email = st.text_input("Email", value=email)

    submitted_profile = st.form_submit_button("Update Profile")

    if submitted_profile:
        updates, errors = build_profile_updates(
            user_doc=user_doc,
            first_name=new_first_name,
            last_name=new_last_name,
            email=new_email,
            lookup_user_by_email=get_user_by_email,
        )

        if errors:
            for field, msg in errors.items():
                st.error(f"{field.replace('_', ' ').capitalize()}: {msg}")
        else:
            old_email = str(user_doc.get("email", "") or "").strip()
            result = update_user(user_doc["_id"], updates)
            if result is None:
                st.error("Failed to update profile (database unavailable).")
            elif getattr(result, "matched_count", 0) != 1:
                st.error(
                    "Could not update profile (your account was not found in the database)."
                )
            elif getattr(result, "modified_count", 0) != 1:
                st.error(
                    "Profile update did not apply (no changes were written). Please try again."
                )
            else:
                # Keep session + authenticator credentials in sync so the user can
                # keep using the app without restarting.
                new_email_value = str(updates.get("email", "") or "").strip()
                old_key = old_email.lower()
                new_key = new_email_value.lower() if new_email_value else old_key

                raw = st.session_state.get("_raw_users")
                if isinstance(raw, dict):
                    try:
                        store = raw.get("usernames", {})
                        if isinstance(store, dict):
                            user_info = store.pop(old_key, None)
                            if isinstance(user_info, dict):
                                user_info["first_name"] = updates["first_name"]
                                user_info["last_name"] = updates["last_name"]
                                user_info["name"] = updates["name"]
                                user_info["email"] = updates["email"]
                                store[new_key] = user_info
                            else:
                                # If we can't find the existing raw doc, just ensure
                                # the key exists with minimal info.
                                store[new_key] = {
                                    "first_name": updates["first_name"],
                                    "last_name": updates["last_name"],
                                    "name": updates["name"],
                                    "email": updates["email"],
                                    "roles": st.session_state.get("roles", []),
                                }
                    except Exception:
                        logging.exception(
                            "Failed to sync raw user info in session state"
                        )

                authenticator = st.session_state.get("authenticator")
                if authenticator is not None:
                    try:
                        users = authenticator.credentials.get("usernames", {})
                        if isinstance(users, dict):
                            existing_creds = users.pop(old_key, None)
                            if not isinstance(existing_creds, dict):
                                existing_creds = {}
                            existing_password = existing_creds.get("password")
                            if not existing_password:
                                existing_password = user_doc.get("password_hash")

                            users[new_key] = {
                                "email": updates["email"],
                                "name": updates["name"],
                                "password": existing_password,
                            }
                    except Exception:
                        logging.exception(
                            "Failed to sync authenticator credentials in session state"
                        )

                st.session_state["username"] = new_key
                st.session_state["email"] = updates["email"]
                st.session_state["name"] = updates["name"]

                st.success("Profile updated successfully.")
                st.rerun()

st.subheader("Change Password")
with st.form("change_password_form"):
    current_password = st.text_input("Current Password", type="password")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm New Password", type="password")

    submitted = st.form_submit_button("Update Password")

    if submitted:
        updates, errors = build_password_change_updates(
            user_doc=user_doc,
            current_password=current_password,
            new_password=new_password,
            confirm_password=confirm_password,
        )

        if errors:
            for field, msg in errors.items():
                st.error(f"{field.replace('_', ' ').capitalize()}: {msg}")
        else:
            updates["force_password_change"] = False
            result = update_user(user_doc["_id"], updates)
            if result is None:
                st.error("Failed to update password (database unavailable).")
            elif getattr(result, "matched_count", 0) != 1:
                st.error(
                    "Could not update password (your account was not found in the database)."
                )
            elif getattr(result, "modified_count", 0) != 1:
                st.error(
                    "Password update did not apply (no changes were written). Please try again."
                )
            else:
                refreshed = get_user_by_email(email)
                if refreshed is None:
                    st.error(
                        "Password may not have saved correctly (could not reload account)."
                    )
                    st.stop()

                refreshed = cast(dict[str, Any], refreshed)
                refreshed_hash_value = refreshed.get("password_hash")
                if (
                    not isinstance(refreshed_hash_value, str)
                    or not refreshed_hash_value
                ):
                    st.error(
                        "Password may not have saved correctly (missing password hash after update)."
                    )
                    st.stop()

                refreshed_hash = cast(str, refreshed_hash_value)

                if not verify_password(new_password, refreshed_hash):
                    st.error(
                        "Password may not have saved correctly (verification failed after update)."
                    )
                    st.stop()

                # Keep the in-memory authenticator credentials in sync so a user can
                # log out and back in without restarting the app.
                raw = st.session_state.get("_raw_users")
                if isinstance(raw, dict):
                    try:
                        raw["usernames"][email]["password_hash"] = updates[
                            "password_hash"
                        ]
                        raw["usernames"][email]["force_password_change"] = False
                    except Exception:
                        logging.exception(
                            "Failed to sync password hash in session state"
                        )

                authenticator = st.session_state.get("authenticator")
                if authenticator is not None:
                    try:
                        authenticator.credentials["usernames"][email]["password"] = (
                            updates["password_hash"]
                        )
                    except Exception:
                        logging.exception(
                            "Failed to sync authenticator credentials in session state"
                        )

                st.success("Password updated successfully.")

                if user_doc.get("force_password_change"):
                    st.session_state["post_password_reset_redirect"] = (
                        "attendance_submission"
                    )
                    st.rerun()
