import json
import os
import streamlit as st
import streamlit_authenticator as stauth
from config.settings import AUTH_COOKIE_KEY


_USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "auth", "users.json")


def _load_credentials() -> tuple[dict[str, dict[str, str]], dict]:
    # TODO: Replace me with loading from mongo!
    with open(_USERS_PATH) as f:
        data = json.load(f)
    credentials = {"usernames": {}}
    for username, info in data["usernames"].items():
        credentials["usernames"][username] = {
            "email": info.get("email", ""),
            "name": info["name"],
            "password": info["password"],
        }
    return credentials, data


def init_auth():
    """Load users and render the login widget. Call once per page that needs auth."""
    if "authenticator" not in st.session_state:
        credentials, raw = _load_credentials()
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
    """Return {"username", "name", "role"} if authenticated, else None."""
    if not st.session_state.get("authentication_status"):
        return None
    username = st.session_state.get("username")
    raw = st.session_state.get("_raw_users", {})
    user_info = raw.get("usernames", {}).get(username, {})
    return {
        "username": username,
        "name": st.session_state.get("name", ""),
        "role": user_info.get("role", "unknown"),
    }


def require_auth():
    """Redirect to login if not authenticated. Call at top of protected pages."""
    if not st.session_state.get("authentication_status"):
        st.switch_page("pages/0_Login.py")


def require_role(*roles):
    """Redirect to login if not authenticated or if user lacks one of the given roles."""
    require_auth()
    user = get_current_user()
    if user is None or user["role"] not in roles:
        st.error("You do not have permission to view this page.")
        st.stop()
