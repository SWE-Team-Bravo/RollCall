from unittest.mock import patch

import pandas as pd

from services.cadets import get_cadet_export_df, validate_cadet_input


def test_valid_input_returns_true():
    ok, msg = validate_cadet_input("John", "Doe", "john.doe@example.com")
    assert ok is True
    assert msg == ""


def test_empty_first_name_returns_false():
    ok, msg = validate_cadet_input("", "Doe", "john@example.com")
    assert ok is False
    assert msg != ""


def test_empty_last_name_returns_false():
    ok, msg = validate_cadet_input("John", "", "john@example.com")
    assert ok is False
    assert msg != ""


def test_empty_email_returns_false():
    ok, msg = validate_cadet_input("John", "Doe", "")
    assert ok is False
    assert msg != ""


def test_all_empty_returns_false():
    ok, msg = validate_cadet_input("", "", "")
    assert ok is False


def test_invalid_email_returns_false():
    ok, msg = validate_cadet_input("John", "Doe", "not-an-email")
    assert ok is False
    assert "email" in msg.lower()


def test_email_without_tld_returns_false():
    ok, msg = validate_cadet_input("John", "Doe", "john@example")
    assert ok is False


def test_first_name_with_numbers_returns_false():
    ok, msg = validate_cadet_input("J0hn", "Doe", "john@example.com")
    assert ok is False
    assert "first name" in msg.lower()


def test_last_name_with_numbers_returns_false():
    ok, msg = validate_cadet_input("John", "D0e", "john@example.com")
    assert ok is False
    assert "last name" in msg.lower()


def test_hyphenated_last_name_is_valid():
    ok, msg = validate_cadet_input("Mary", "Smith-Jones", "mary@example.com")
    assert ok is True
    assert msg == ""


def test_apostrophe_in_last_name_is_valid():
    ok, msg = validate_cadet_input("John", "O'Brien", "john@example.com")
    assert ok is True
    assert msg == ""


def test_hyphenated_first_name_is_valid():
    ok, msg = validate_cadet_input("Mary-Jane", "Watson", "mj@example.com")
    assert ok is True
    assert msg == ""


def test_first_name_with_special_chars_returns_false():
    ok, msg = validate_cadet_input("John!", "Doe", "john@example.com")
    assert ok is False


def test_last_name_with_space_is_valid():
    ok, msg = validate_cadet_input("John", "Van Der Berg", "john@example.com")
    assert ok is True


def test_valid_kent_edu_email():
    ok, msg = validate_cadet_input("Tyler", "Brooks", "tbrooks@kent.edu")
    assert ok is True
    assert msg == ""


def test_first_name_with_leading_space_returns_false():
    ok, msg = validate_cadet_input(" John", "Doe", "john@example.com")
    assert ok is False


def test_last_name_with_trailing_space_returns_false():
    ok, msg = validate_cadet_input("John", "Doe ", "john@example.com")
    assert ok is False


def test_email_with_plus_addressing_is_valid():
    ok, msg = validate_cadet_input("Jane", "Doe", "jane+tag@example.com")
    assert ok is True


def test_get_cadet_export_df_uses_user_names_and_email():
    cadets = [
        {
            "_id": "c1",
            "user_id": "u1",
            "rank": "200/250/500 (sophomore)",
            "first_name": "(stale)",
            "last_name": "(stale)",
            "email": "(stale)",
        }
    ]
    user = {
        "_id": "u1",
        "first_name": "Tyler",
        "last_name": "Brooks",
        "email": "cadet1@rollcall.local",
    }

    with (
        patch("services.cadets.get_all_cadets", return_value=cadets),
        patch("services.cadets.get_user_by_id", return_value=user),
    ):
        df = get_cadet_export_df()

    assert isinstance(df, pd.DataFrame)
    assert df["First Name"].iloc[0] == "Tyler"
    assert df["Last Name"].iloc[0] == "Brooks"
    assert df["Email"].iloc[0] == "cadet1@rollcall.local"
