from services.admin_users import (
    summarize_user,
    list_users_for_admin,
    validate_new_user_data,
    build_update_user_payload,
    count_enabled_admins,
    validate_disable_user,
    confirm_destructive_action,
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
        "name": "New Admin",
        "email": "admin@example.com",
        # Primary role updated to admin; existing secondary role preserved.
        "roles": ["admin", "cadet"],
    }


def test_build_update_user_payload_preserves_additional_roles():
    existing_user = {
        "_id": "u2",
        "first_name": "Multi",
        "last_name": "Role",
        "email": "multi@example.com",
        "roles": ["admin", "cadre"],
    }

    # No other user has this email, so uniqueness is satisfied.
    other_emails: set[str] = set()

    # Changing the primary role to "cadre" should keep both roles,
    # just reorder so "cadre" is primary.
    updates, errors = build_update_user_payload(
        existing_user=existing_user,
        new_first_name="",
        new_last_name="",
        new_email="",
        new_role="cadre",
        other_emails=other_emails,
    )

    assert errors == {}
    assert updates["roles"] == ["cadre", "admin"]


def test_summarize_user_detects_waiver_reviewer_tag():
    user_doc = {
        "_id": "u1",
        "first_name": "Tyler",
        "last_name": "Brooks",
        "email": "tyler@rollcall.local",
        "roles": ["cadet", "waiver_reviewer"],
    }
    summary = summarize_user(user_doc)
    assert summary["waiver_reviewer"] is True
    assert summary["role"] == "cadet"


def test_summarize_user_waiver_reviewer_false_when_absent():
    user_doc = {
        "_id": "u2",
        "email": "plain@rollcall.local",
        "roles": ["cadet"],
    }
    summary = summarize_user(user_doc)
    assert summary["waiver_reviewer"] is False


def test_summarize_user_marks_disabled_accounts():
    summary = summarize_user(
        {
            "_id": "u3",
            "first_name": "Dana",
            "last_name": "Disabled",
            "email": "disabled@example.com",
            "roles": ["cadet"],
            "disabled": True,
        }
    )

    assert summary["disabled"] is True
    assert summary["status"] == "Disabled"
    assert "[Disabled]" in summary["name"]


def test_count_enabled_admins_ignores_disabled_admins():
    assert count_enabled_admins(
        [
            {"roles": ["admin"]},
            {"roles": ["admin"], "disabled": True},
            {"roles": ["cadet"]},
        ]
    ) == 1


def test_build_update_user_payload_adds_waiver_reviewer():
    existing_user = {
        "_id": "u1",
        "first_name": "Tyler",
        "last_name": "Brooks",
        "email": "tyler@rollcall.local",
        "roles": ["cadet"],
    }
    updates, errors = build_update_user_payload(
        existing_user=existing_user,
        new_first_name="Tyler",
        new_last_name="Brooks",
        new_email="tyler@rollcall.local",
        new_role="cadet",
        other_emails=set(),
        waiver_reviewer=True,
    )
    assert errors == {}
    assert "waiver_reviewer" in updates["roles"]
    assert updates["roles"][0] == "cadet"


def test_build_update_user_payload_removes_waiver_reviewer():
    existing_user = {
        "_id": "u1",
        "first_name": "Tyler",
        "last_name": "Brooks",
        "email": "tyler@rollcall.local",
        "roles": ["cadet", "waiver_reviewer"],
    }
    updates, errors = build_update_user_payload(
        existing_user=existing_user,
        new_first_name="Tyler",
        new_last_name="Brooks",
        new_email="tyler@rollcall.local",
        new_role="cadet",
        other_emails=set(),
        waiver_reviewer=False,
    )
    assert errors == {}
    assert "waiver_reviewer" not in updates["roles"]


def test_confirm_destructive_action_requires_exact_keyword():
    assert confirm_destructive_action("DELETE") is True
    assert confirm_destructive_action("  DELETE  ") is True
    assert confirm_destructive_action("delete") is False
    assert confirm_destructive_action("Delete") is False
    assert confirm_destructive_action("del") is False
    assert confirm_destructive_action("DELETE EVERYTHING") is False


def test_validate_disable_user_blocks_self_disable():
    admin = {"_id": "a1", "roles": ["admin"]}
    error = validate_disable_user(admin, admin, [admin])
    assert error == "You cannot disable your own account."


def test_validate_disable_user_blocks_last_admin():
    admin = {"_id": "a1", "roles": ["admin"]}
    actor = {"_id": "a2", "roles": ["admin"]}
    error = validate_disable_user(admin, actor, [admin])
    assert error == "You cannot disable the last enabled admin user."


def test_validate_disable_user_allows_disable_with_other_admins():
    admin1 = {"_id": "a1", "roles": ["admin"]}
    admin2 = {"_id": "a2", "roles": ["admin"]}
    error = validate_disable_user(admin1, admin2, [admin1, admin2])
    assert error is None


def test_validate_disable_user_allows_non_admin_disable():
    cadet = {"_id": "c1", "roles": ["cadet"]}
    actor = {"_id": "a1", "roles": ["admin"]}
    error = validate_disable_user(cadet, actor, [cadet, actor])
    assert error is None
