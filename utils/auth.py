import streamlit as st
import streamlit_authenticator as stauth
from config.settings import AUTH_COOKIE_KEY
from utils.db import get_collection


def _load_credentials() -> tuple[dict[str, dict[str, str]], dict]:
    collection = get_collection("users")
    if collection is None:
        st.error("Database unavailable — cannot authenticate.")
        st.stop()

    assert collection is not None

    raw = {"usernames": {}}
    credentials = {"usernames": {}}
    for doc in collection.find({}, {"_id": 0}):
        username = doc["username"]
        raw["usernames"][username] = doc
        credentials["usernames"][username] = {
            "email": doc.get("email", ""),
            "name": doc["name"],
            "password": doc["password"],
        }
    return credentials, raw


def init_auth():
    if "authenticator" not in st.session_state:
        credentials, raw = _load_credentials()

        assert AUTH_COOKIE_KEY is not None

        authenticator = stauth.Authenticate(
            credentials,
            cookie_name="rollcall_auth",
            cookie_key=AUTH_COOKIE_KEY,
            cookie_expiry_days=1,
            auto_hash=False,
        )
        st.session_state["authenticator"] = authenticator
        st.session_state["_raw_users"] = raw
    else:
        authenticator = st.session_state["authenticator"]

    authenticator.login(location="main")
    return authenticator


def get_current_user() -> dict[str, str] | None:
    if not st.session_state.get("authentication_status"):
        return None
    username = st.session_state.get("username")
    raw = st.session_state.get("_raw_users", {})
    user_info = raw.get("usernames", {}).get(username, {})
    return {
        "username": str(username),
        "name": str(st.session_state.get("name", "")),
        "role": str(user_info.get("role", "unknown")),
    }


def require_auth():
    if not st.session_state.get("authentication_status"):
        st.switch_page("pages/0_Login.py")


def require_role(*roles):
    require_auth()
    user = get_current_user()
    if user is None or user["role"] not in roles:
        st.error("You do not have permission to view this page.")
        st.stop()
