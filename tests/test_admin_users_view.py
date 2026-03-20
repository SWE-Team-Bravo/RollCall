from utils.admin_users import (
    summarize_user,
    list_users_for_admin,
    validate_new_user_data,
    build_update_user_payload,
    confirm_delete_user,
)


def test_summarize_user_uses_name_and_primary_role():
    user_doc = {
        "_id": "user1",
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin1@example.com",
        "roles": ["admin", "cadre"],
    }

    summary = summarize_user(user_doc)

    assert summary["id"] == "user1"
    assert summary["email"] == "admin1@example.com"
    assert summary["name"] == "Admin User"
    assert summary["role"] == "admin"


def test_list_users_for_admin_sorts_by_email_and_summarizes():
    users = [
        {
            "_id": "u2",
            "first_name": "Zed",
            "last_name": "User",
            "email": "zed@example.com",
            "roles": ["cadre"],
        },
        {
            "_id": "u1",
            "first_name": "Alice",
            "last_name": "Admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        },
    ]

    summaries = list_users_for_admin(users)

    # Sorted by email: admin@example.com comes before zed@example.com
    assert [s["email"] for s in summaries] == [
        "admin@example.com",
        "zed@example.com",
    ]

    # Each entry is a normalized summary
    first = summaries[0]
    assert first["id"] == "u1"
    assert first["name"] == "Alice Admin"
    assert first["role"] == "admin"


def test_validate_new_user_data_success():
    existing_emails = {"existing@example.com"}

    payload, errors = validate_new_user_data(
        first_name="New",
        last_name="Admin",
        email="new.admin@example.com",
        password="strongpass",
        role="admin",
        existing_emails=existing_emails,
    )

    assert errors == {}
    assert payload == {
        "first_name": "New",
        "last_name": "Admin",
        "email": "new.admin@example.com",
        "password": "strongpass",
        "roles": ["admin"],
    }


def test_validate_new_user_data_rejects_duplicate_email():
    existing_emails = {"admin@example.com"}

    payload, errors = validate_new_user_data(
        first_name="Another",
        last_name="Admin",
        email="admin@example.com",
        password="strongpass",
        role="admin",
        existing_emails=existing_emails,
    )

    assert payload == {}
    assert "email" in errors
    assert "already exists" in errors["email"].lower()


def test_validate_new_user_data_rejects_short_password_and_invalid_role():
    payload, errors = validate_new_user_data(
        first_name="New",
        last_name="User",
        email="new.user@example.com",
        password="short",
        role="not_a_role",
        existing_emails=set(),
    )

    assert payload == {}
    assert "password" in errors
    assert "at least 8 characters" in errors["password"].lower()
    assert "role" in errors
    assert "invalid" in errors["role"].lower()


def test_build_update_user_payload_updates_name_email_and_role():
    existing_user = {
        "_id": "u1",
        "first_name": "Old",
        "last_name": "Name",
        "email": "old@example.com",
        "roles": ["cadet"],
    }

    # Simulate that another user already has other@example.com, so
    # new email must not collide with that.
    other_emails = {"other@example.com"}

    updates, errors = build_update_user_payload(
        existing_user=existing_user,
        new_first_name="New",
        new_last_name="Admin",
        new_email="admin@example.com",
        new_role="admin",
        other_emails=other_emails,
    )

    assert errors == {}
    assert updates == {
        "first_name": "New",
        "last_name": "Admin",
        "email": "admin@example.com",
        "roles": ["admin"],
    }


def test_confirm_delete_user_requires_exact_keyword():
    # Only the exact keyword (case-insensitive, trimmed) should allow delete.
    assert confirm_delete_user("DELETE") is True
    assert confirm_delete_user("  delete  ") is True
    assert confirm_delete_user("del") is False
    assert confirm_delete_user("DELETE EVERYTHING") is False
