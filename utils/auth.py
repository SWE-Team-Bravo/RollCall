import streamlit as st
import streamlit_authenticator as stauth
from config.settings import AUTH_COOKIE_KEY
from utils.auth_logic import (
    build_credentials_from_docs,
    extract_user_from_raw,
    user_has_any_role,
)
from utils.db import get_collection


def _load_credentials() -> tuple[dict[str, dict[str, str]], dict]:
    collection = get_collection("users")
    if collection is None:
        st.error("Database unavailable — cannot authenticate.")
        st.stop()

    assert collection is not None

    return build_credentials_from_docs(list(collection.find({}, {"_id": 0})))


def init_auth():
    # Always load credentials from the DB so changes (like password updates)
    # take effect immediately without requiring a server restart.
    credentials, raw = _load_credentials()

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
        # Keep the in-memory authenticator store consistent with the DB.
        try:
            authenticator.credentials = credentials
        except Exception:
            pass

    st.session_state["_raw_users"] = raw

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
