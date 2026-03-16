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
        email = doc["email"]
        raw["usernames"][email] = doc
        credentials["usernames"][email] = {
            "email": email,
            "name": f"{doc['first_name']} {doc['last_name']}".strip(),
            "password": doc["password_hash"],
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


def get_current_user() -> dict | None:
    if not st.session_state.get("authentication_status"):
        return None
    email = st.session_state.get("username")
    raw = st.session_state.get("_raw_users", {})
    user_info = raw.get("usernames", {}).get(email, {})
    return {
        "email": str(email),
        "first_name": str(user_info.get("first_name", "")),
        "last_name": str(user_info.get("last_name", "")),
        "roles": list(user_info.get("roles", [])),
    }


def require_auth():
    if not st.session_state.get("authentication_status"):
        st.switch_page("pages/0_Login.py")


def require_role(*roles: str):
    require_auth()
    user = get_current_user()
    if user is None or not set(user["roles"]) & set(roles):
        st.error("You do not have permission to view this page.")
        st.stop()
