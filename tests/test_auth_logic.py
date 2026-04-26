from utils.auth_logic import (
    build_credentials_from_docs,
    extract_user_from_raw,
    user_has_any_role,
)


def _doc(email="tj@example.com", first="TJ", last="Raklovits", pw="hashed", roles=None):
    return {
        "email": email,
        "first_name": first,
        "last_name": last,
        "password_hash": pw,
        "roles": roles or ["cadet"],
    }


# --- build_credentials_from_docs ---


def test_credentials_contains_email_key():
    credentials, _ = build_credentials_from_docs([_doc()])
    assert "tj@example.com" in credentials["usernames"]


def test_credentials_name_is_full_name():
    credentials, _ = build_credentials_from_docs([_doc()])
    assert credentials["usernames"]["tj@example.com"]["name"] == "TJ Raklovits"


def test_credentials_password_is_hash():
    credentials, _ = build_credentials_from_docs([_doc(pw="bcrypthash")])
    assert credentials["usernames"]["tj@example.com"]["password"] == "bcrypthash"


def test_raw_contains_full_doc():
    doc = _doc()
    _, raw = build_credentials_from_docs([doc])
    assert raw["usernames"]["tj@example.com"] is doc


def test_multiple_users_all_present():
    docs = [_doc("a@x.com"), _doc("b@x.com")]
    credentials, raw = build_credentials_from_docs(docs)
    assert "a@x.com" in credentials["usernames"]
    assert "b@x.com" in credentials["usernames"]
    assert "a@x.com" in raw["usernames"]
    assert "b@x.com" in raw["usernames"]


def test_empty_docs_returns_empty_dicts():
    credentials, raw = build_credentials_from_docs([])
    assert credentials == {"usernames": {}}
    assert raw == {"usernames": {}}


def test_disabled_users_are_excluded_from_credentials_but_in_raw():
    credentials, raw = build_credentials_from_docs(
        [
            _doc(email="active@example.com"),
            _doc(email="disabled@example.com") | {"disabled": True},
        ]
    )
    assert "active@example.com" in credentials["usernames"]
    assert "disabled@example.com" not in credentials["usernames"]
    assert "disabled@example.com" in raw["usernames"]


def test_name_stripped_when_no_last_name():
    doc = _doc(first="TJ", last="")
    credentials, _ = build_credentials_from_docs([doc])
    assert credentials["usernames"]["tj@example.com"]["name"] == "TJ"


# --- extract_user_from_raw ---


def test_returns_user_dict_for_known_email():
    _, raw = build_credentials_from_docs([_doc(roles=["admin"])])
    user = extract_user_from_raw("tj@example.com", raw)
    assert user is not None
    assert user["email"] == "tj@example.com"
    assert user["first_name"] == "TJ"
    assert user["last_name"] == "Raklovits"
    assert user["roles"] == ["admin"]


def test_returns_none_for_unknown_email():
    _, raw = build_credentials_from_docs([_doc()])
    assert extract_user_from_raw("nobody@example.com", raw) is None


def test_returns_none_for_none_email():
    _, raw = build_credentials_from_docs([_doc()])
    assert extract_user_from_raw(None, raw) is None


def test_returns_none_for_empty_email():
    _, raw = build_credentials_from_docs([_doc()])
    assert extract_user_from_raw("", raw) is None


def test_missing_roles_defaults_to_empty_list():
    doc = {
        "email": "x@x.com",
        "first_name": "A",
        "last_name": "B",
        "password_hash": "h",
    }
    _, raw = build_credentials_from_docs([doc])
    user = extract_user_from_raw("x@x.com", raw)
    assert user is not None
    assert user["roles"] == []


def test_extract_user_from_raw_includes_disabled_flag():
    _, raw = build_credentials_from_docs([_doc()])
    user = extract_user_from_raw("tj@example.com", raw)
    assert user is not None
    assert user["disabled"] is False


# --- user_has_any_role ---


def test_user_with_matching_role_returns_true():
    user = {"roles": ["admin", "cadet"]}
    assert user_has_any_role(user, ("admin",)) is True


def test_user_without_matching_role_returns_false():
    user = {"roles": ["cadet"]}
    assert user_has_any_role(user, ("admin",)) is False


def test_none_user_returns_false():
    assert user_has_any_role(None, ("admin",)) is False


def test_empty_roles_returns_false():
    assert user_has_any_role({"roles": []}, ("admin",)) is False


def test_any_of_multiple_required_roles_matches():
    user = {"roles": ["flight_commander"]}
    assert user_has_any_role(user, ("admin", "flight_commander")) is True


def test_no_overlap_returns_false():
    user = {"roles": ["cadet"]}
    assert user_has_any_role(user, ("admin", "flight_commander")) is False


def test_user_with_multiple_roles_one_matches():
    user = {"roles": ["cadet", "admin"]}
    assert user_has_any_role(user, ("admin",)) is True


def test_disabled_users_excluded_from_credentials():
    active = _doc("active@example.com")
    disabled = _doc("disabled@example.com")
    disabled["disabled"] = True

    credentials, raw = build_credentials_from_docs([active, disabled])

    assert "active@example.com" in credentials["usernames"]
    assert "disabled@example.com" not in credentials["usernames"]
    assert "disabled@example.com" in raw["usernames"]
