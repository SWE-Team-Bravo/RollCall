import time

import streamlit as st
from typing import Any, cast

from config.settings import AUTH_COOKIE_KEY
from utils.auth import get_current_user, init_auth
from utils.db_schema_crud import get_user_by_email, update_user
from utils.password import hash_password
from utils.password_reset import (
    PASSWORD_RESET_TOKEN_EXPIRES_IN_SECONDS,
    generate_password_reset_token,
    validate_password_reset_token,
)
from utils.password_reset_email import send_password_reset_email


def _get_query_param(name: str) -> str | None:
    # Prefer the stable Streamlit API `st.query_params`.
    # Use `getattr` for backwards compatibility without tripping static type checkers.
    qp: Any = getattr(st, "query_params", None)
    if qp is not None:
        try:
            value = qp.get(name)
            if isinstance(value, list):
                return value[0] if value else None
            return value
        except Exception:
            pass

    exp_get = getattr(st, "experimental_get_query_params", None)
    if callable(exp_get):
        try:
            qp = exp_get()
            value = qp.get(name)
            if isinstance(value, list):
                return value[0] if value else None
            return value
        except Exception:
            return None

    return None


def _clear_reset_query_params() -> None:
    qp: Any = getattr(st, "query_params", None)
    if qp is not None and hasattr(qp, "clear"):
        try:
            qp.clear()
            return
        except Exception:
            pass

    exp_set = getattr(st, "experimental_set_query_params", None)
    if callable(exp_set):
        try:
            exp_set()
        except Exception:
            pass


st.title("Login")

reset_token = (_get_query_param("reset_token") or "").strip()
reset_email_param = (_get_query_param("email") or "").strip()

if reset_token:
    st.subheader("Reset password")

    email = st.text_input("Email", value=reset_email_param)
    new_pw = st.text_input("New password", type="password")
    confirm_pw = st.text_input("Confirm new password", type="password")

    col1, col2 = st.columns([2, 8])
    with col1:
        submitted = st.button("Reset", type="primary")
    with col2:
        if st.button("Back to login"):
            _clear_reset_query_params()
            st.rerun()

    if submitted:
        auth_cookie_key = AUTH_COOKIE_KEY
        if not auth_cookie_key:
            st.error("Password reset is not configured (missing AUTH_COOKIE_KEY).")
            st.stop()
        auth_cookie_key = cast(str, auth_cookie_key)

        if not email:
            st.error("Email is required.")
        elif not new_pw:
            st.error("New password is required.")
        elif len(new_pw) < 8:
            st.error("Password must be at least 8 characters long.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match.")
        else:
            user_doc = get_user_by_email(email)
            if not user_doc:
                st.error("Invalid reset link/token.")
            else:
                claims = validate_password_reset_token(
                    token=reset_token,
                    secret=auth_cookie_key,
                    expected_email=str(user_doc.get("email", "") or ""),
                    current_password_changed_at=user_doc.get("password_changed_at"),
                )
                if not claims:
                    st.error("Invalid or expired reset token.")
                else:
                    updates = {
                        "password_hash": hash_password(new_pw),
                        "password_changed_at": int(time.time()),
                    }
                    result = update_user(user_doc["_id"], updates)
                    if result is None:
                        st.error("Failed to reset password (database unavailable).")
                    else:
                        st.success("Password reset successfully. You can now log in.")
                        _clear_reset_query_params()
                        st.rerun()

    st.stop()


authenticator = init_auth()

if st.session_state.get("authentication_status") is False:
    st.error("Incorrect username or password.")


with st.expander("Forgot password?", expanded=False):
    st.caption("Enter your email and we’ll send a time-limited reset token.")

    fp_email = st.text_input("Email address", key="forgot_pw_email")
    if st.button("Send reset token", key="forgot_pw_send"):
        # Do not reveal whether the email exists.
        auth_cookie_key = AUTH_COOKIE_KEY
        if not auth_cookie_key:
            st.error("Password reset is not configured (missing AUTH_COOKIE_KEY).")
        else:
            auth_cookie_key = cast(str, auth_cookie_key)
            user_doc = get_user_by_email(fp_email.strip()) if fp_email else None
            if user_doc and user_doc.get("email"):
                token = generate_password_reset_token(
                    email=str(user_doc.get("email")),
                    secret=auth_cookie_key,
                    expires_in_seconds=PASSWORD_RESET_TOKEN_EXPIRES_IN_SECONDS,
                    password_changed_at=user_doc.get("password_changed_at"),
                )
                send_password_reset_email(
                    to_email=str(user_doc.get("email")), token=token
                )

            st.success(
                "If an account exists for that email, a reset link has been sent."
            )


user = get_current_user()
if user:
    st.success(
        f"Logged in as **{user['first_name']} {user['last_name']}** ({', '.join(user['roles'])})"
    )
    if st.button("Go to Home"):
        st.switch_page("Home.py")
    authenticator.logout("Logout", location="main")
