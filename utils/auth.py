from datetime import datetime

import jwt
import streamlit as st
import streamlit_authenticator as stauth
from jwt import DecodeError, InvalidSignatureError

from config.settings import AUTH_COOKIE_KEY
from utils.auth_logic import (
    build_credentials_from_docs,
    extract_user_from_raw,
    user_has_any_role,
)
from utils.db import get_collection

_COOKIE_NAME = "rollcall_auth"


def _load_credentials() -> tuple[dict[str, dict[str, str]], dict]:
    collection = get_collection("users")
    if collection is None:
        st.error("Database unavailable — cannot authenticate.")
        st.stop()

    assert collection is not None

    return build_credentials_from_docs(list(collection.find({}, {"_id": 0})))


def _get_or_create_authenticator() -> stauth.Authenticate:
    credentials, raw = _load_credentials()
    st.session_state["_raw_users"] = raw

    assert AUTH_COOKIE_KEY is not None

    if "authenticator" not in st.session_state:
        authenticator = stauth.Authenticate(
            credentials,
            cookie_name="rollcall_auth",
            cookie_key=AUTH_COOKIE_KEY,
            cookie_expiry_days=1,
            auto_hash=False,
        )
        st.session_state["authenticator"] = authenticator
    else:
        authenticator = st.session_state["authenticator"]
        try:
            authenticator.credentials = credentials
        except Exception:
            pass

    return authenticator


def restore_session() -> None:
    if st.session_state.get("authentication_status"):
        return

    raw_token = st.context.cookies.get(_COOKIE_NAME)
    if not raw_token:
        return

    assert AUTH_COOKIE_KEY is not None
    try:
        token = jwt.decode(raw_token, AUTH_COOKIE_KEY, algorithms=["HS256"])
    except (DecodeError, InvalidSignatureError):
        return

    username = token.get("username")
    exp_date = token.get("exp_date", 0)
    if not username or exp_date <= datetime.now().timestamp():
        return

    credentials, raw = _load_credentials()
    if username not in credentials.get("usernames", {}):
        return

    raw_user = raw.get("usernames", {}).get(username)
    if not raw_user:
        return

    st.session_state["_raw_users"] = raw
    st.session_state["name"] = (
        f"{raw_user.get('first_name', '')} {raw_user.get('last_name', '')}".strip()
    )
    st.session_state["username"] = username
    st.session_state["authentication_status"] = True
    st.session_state["email"] = raw_user.get("email")
    st.session_state["roles"] = raw_user.get("roles")
    st.session_state.setdefault("logout", None)


def ensure_authenticator() -> stauth.Authenticate:
    """Ensure the authenticator exists in session state and return it."""
    return _get_or_create_authenticator()


def init_auth():
    authenticator = _get_or_create_authenticator()

    authenticator.login(location="main")
    if st.session_state.get("authentication_status") is False:
        st.error("Incorrect username or password.")
    return authenticator


def get_current_user() -> dict | None:
    if not st.session_state.get("authentication_status"):
        return None
    email = st.session_state.get("username")
    raw = st.session_state.get("_raw_users", {})
    return extract_user_from_raw(email, raw)


def require_auth():
    if not st.session_state.get("authentication_status"):
        st.error("You must be logged in to view this page.")
        st.stop()


def require_role(*roles: str):
    require_auth()
    user = get_current_user()
    if not user_has_any_role(user, roles):
        st.error("You do not have permission to view this page.")
        st.stop()
