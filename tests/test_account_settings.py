from services.account_settings import (
    build_password_change_updates,
    build_profile_updates,
)
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


def test_profile_rejects_empty_first_name():
    user_doc = {
        "_id": "user1",
        "email": "user@example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="   ",
        last_name="Brooks",
        email="user@example.com",
        lookup_user_by_email=lambda e: None,
    )

    assert updates == {}
    assert "first_name" in errors


def test_profile_rejects_empty_last_name():
    user_doc = {
        "_id": "user1",
        "email": "user@example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="Tyler",
        last_name="\t\n",
        email="user@example.com",
        lookup_user_by_email=lambda e: None,
    )

    assert updates == {}
    assert "last_name" in errors


def test_profile_rejects_invalid_email():
    user_doc = {
        "_id": "user1",
        "email": "user@example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="Tyler",
        last_name="Brooks",
        email="not-an-email",
        lookup_user_by_email=lambda e: None,
    )

    assert updates == {}
    assert "email" in errors


def test_profile_rejects_duplicate_email():
    user_doc = {
        "_id": "user1",
        "email": "user@example.com",
    }
    other_user = {
        "_id": "user2",
        "email": "other@example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="Tyler",
        last_name="Brooks",
        email="Other@Example.com",
        lookup_user_by_email=lambda e: other_user,
    )

    assert updates == {}
    assert "email" in errors
    assert "already" in errors["email"].lower()


def test_profile_allows_keep_same_email_case_insensitive():
    user_doc = {
        "_id": "user1",
        "email": "User@Example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="Tyler",
        last_name="Brooks",
        email="user@example.com",
        lookup_user_by_email=lambda e: {
            "_id": "user1",
            "email": "User@Example.com",
        },
    )

    assert errors == {}
    assert updates["email"] == "user@example.com"


def test_profile_success_returns_updates_and_syncs_name():
    user_doc = {
        "_id": "user1",
        "email": "user@example.com",
    }

    updates, errors = build_profile_updates(
        user_doc=user_doc,
        first_name="  Tyler ",
        last_name=" Brooks  ",
        email=" tyler.brooks@rollcall.local ",
        lookup_user_by_email=lambda e: None,
    )

    assert errors == {}
    assert updates["first_name"] == "Tyler"
    assert updates["last_name"] == "Brooks"
    assert updates["email"] == "tyler.brooks@rollcall.local"
    assert updates["name"] == "Tyler Brooks"
