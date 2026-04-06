from services.account_settings import build_password_change_updates
from utils.password import hash_password, verify_password


def _user_doc(password: str = "currentpass") -> dict:
    return {
        "_id": "user1",
        "email": "user@example.com",
        "password_hash": hash_password(password),
    }


def test_rejects_wrong_current_password():
    user_doc = _user_doc("correct-current")

    updates, errors = build_password_change_updates(
        user_doc=user_doc,
        current_password="wrong",
        new_password="newpassword",
        confirm_password="newpassword",
    )

    assert updates == {}
    assert "current_password" in errors


def test_rejects_mismatched_new_password_confirmation():
    user_doc = _user_doc()

    updates, errors = build_password_change_updates(
        user_doc=user_doc,
        current_password="currentpass",
        new_password="newpassword",
        confirm_password="different",
    )

    assert updates == {}
    assert "confirm_password" in errors


def test_rejects_short_new_password():
    user_doc = _user_doc()

    updates, errors = build_password_change_updates(
        user_doc=user_doc,
        current_password="currentpass",
        new_password="short",
        confirm_password="short",
    )

    assert updates == {}
    assert "new_password" in errors
    assert "at least 8" in errors["new_password"].lower()


def test_success_returns_password_hash_update():
    user_doc = _user_doc("currentpass")

    updates, errors = build_password_change_updates(
        user_doc=user_doc,
        current_password="currentpass",
        new_password="newpassword",
        confirm_password="newpassword",
    )

    assert errors == {}
    assert set(updates.keys()) == {"password_hash"}
    assert updates["password_hash"] != "newpassword"
    assert updates["password_hash"].startswith("$2")
    assert verify_password("newpassword", updates["password_hash"]) is True
