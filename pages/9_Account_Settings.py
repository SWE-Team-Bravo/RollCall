import streamlit as st
from typing import Any, cast

from services.account_settings import build_password_change_updates
from utils.auth import require_auth, get_current_user
from utils.db_schema_crud import get_user_by_email, update_user
from utils.password import verify_password

require_auth()

st.title("Account Settings")

user = get_current_user()
if user is None:
    st.error("Could not determine the currently logged-in user.")
    st.stop()

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
                    except Exception:
                        pass

                authenticator = st.session_state.get("authenticator")
                if authenticator is not None:
                    try:
                        authenticator.credentials["usernames"][email]["password"] = (
                            updates["password_hash"]
                        )
                    except Exception:
                        pass

                st.success("Password updated successfully.")
