from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest  # type: ignore

_SECRET = "test-secret-key"
_USERNAME = "jdoe"
_USER_DOC = {
    "email": _USERNAME,
    "first_name": "John",
    "last_name": "Doe",
    "password_hash": "$2b$12$placeholder",
    "roles": ["admin"],
}


def _make_token(username: str = _USERNAME, offset_seconds: int = 3600) -> str:
    exp = (datetime.now() + timedelta(seconds=offset_seconds)).timestamp()
    return jwt.encode(
        {"username": username, "exp_date": exp},
        _SECRET,
        algorithm="HS256",
    )


def _credentials_for(username: str, user_doc: dict) -> tuple[dict, dict]:
    credentials = {"usernames": {username: {"password": user_doc["password_hash"]}}}
    raw = {
        "usernames": {
            username: {
                "first_name": user_doc["first_name"],
                "last_name": user_doc["last_name"],
                "email": user_doc["email"],
                "roles": user_doc["roles"],
            }
        }
    }
    return credentials, raw


@pytest.fixture(autouse=True)
def _patch_auth_cookie_key():
    with patch("utils.auth.AUTH_COOKIE_KEY", _SECRET):
        yield


class TestRestoreSession:
    def test_restores_session_from_valid_cookie(self):
        token = _make_token()
        credentials, raw = _credentials_for(_USERNAME, _USER_DOC)

        session: dict = {}

        with (
            patch("utils.auth._load_credentials", return_value=(credentials, raw)),
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {_COOKIE_NAME: token}

            from utils.auth import restore_session

            restore_session()

        assert session.get("authentication_status") is True
        assert session.get("username") == _USERNAME
        assert session.get("name") == "John Doe"
        assert session.get("roles") == ["admin"]
        assert session.get("email") == _USERNAME

    def test_noop_when_already_authenticated(self):
        session = {"authentication_status": True, "username": "existing_user"}

        with (
            patch("utils.auth._load_credentials") as mock_load,
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {}

            from utils.auth import restore_session

            restore_session()

        mock_load.assert_not_called()
        assert session["username"] == "existing_user"

    def test_noop_when_no_cookie(self):
        session: dict = {}

        with (
            patch("utils.auth._load_credentials") as mock_load,
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {}

            from utils.auth import restore_session

            restore_session()

        mock_load.assert_not_called()
        assert "authentication_status" not in session

    def test_ignores_expired_token(self):
        token = _make_token(offset_seconds=-1)  # expired 1 second ago
        credentials, raw = _credentials_for(_USERNAME, _USER_DOC)

        session: dict = {}

        with (
            patch("utils.auth._load_credentials", return_value=(credentials, raw)),
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {_COOKIE_NAME: token}

            from utils.auth import restore_session

            restore_session()

        assert "authentication_status" not in session

    def test_ignores_tampered_token(self):
        token = _make_token() + "tampered"
        session: dict = {}

        with (
            patch("utils.auth._load_credentials") as mock_load,
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {_COOKIE_NAME: token}

            from utils.auth import restore_session

            restore_session()

        mock_load.assert_not_called()
        assert "authentication_status" not in session

    def test_ignores_unknown_username(self):
        token = _make_token(username="ghost")
        credentials, raw = _credentials_for(_USERNAME, _USER_DOC)  # "ghost" not present

        session: dict = {}

        with (
            patch("utils.auth._load_credentials", return_value=(credentials, raw)),
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {_COOKIE_NAME: token}

            from utils.auth import restore_session

            restore_session()

        assert "authentication_status" not in session

    def test_ignores_disabled_user_filtered_from_credentials(self):
        token = _make_token()
        session: dict = {}

        with (
            patch(
                "utils.auth._load_credentials",
                return_value=({"usernames": {}}, {"usernames": {}}),
            ),
            patch("streamlit.context") as mock_ctx,
            patch("streamlit.session_state", session),
        ):
            mock_ctx.cookies = {_COOKIE_NAME: token}

            from utils.auth import restore_session

            restore_session()

        assert "authentication_status" not in session


_COOKIE_NAME = "rollcall_auth"
