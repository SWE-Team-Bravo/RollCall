import time

from utils.password import verify_password


def test_generate_temp_password_has_reasonable_length_and_charset():
    from utils.password_reset import generate_temp_password

    pw = generate_temp_password()
    assert isinstance(pw, str)
    assert len(pw) >= 12
    # Avoid whitespace (easy copy/paste problems)
    assert pw.strip() == pw


def test_build_password_updates_hashes_and_sets_timestamp():
    from utils.password_reset import build_password_updates

    updates, temp = build_password_updates()
    assert "password_hash" in updates
    assert "password_changed_at" in updates
    assert verify_password(temp, updates["password_hash"]) is True


def test_reset_token_round_trip_validation():
    from utils.password_reset import (
        generate_password_reset_token,
        validate_password_reset_token,
    )

    secret = "test-secret"
    email = "user@example.com"
    pwd_changed_at = 123.0

    token = generate_password_reset_token(
        email=email,
        secret=secret,
        expires_in_seconds=60,
        password_changed_at=pwd_changed_at,
    )

    claims = validate_password_reset_token(
        token=token,
        secret=secret,
        expected_email=email,
        current_password_changed_at=pwd_changed_at,
    )
    assert claims is not None
    assert claims["email"].lower() == email.lower()


def test_reset_token_rejected_when_expired():
    from utils.password_reset import (
        generate_password_reset_token,
        validate_password_reset_token,
    )

    secret = "test-secret"
    email = "user@example.com"

    token = generate_password_reset_token(
        email=email,
        secret=secret,
        expires_in_seconds=1,
        password_changed_at=None,
    )
    time.sleep(1.1)

    assert (
        validate_password_reset_token(
            token=token,
            secret=secret,
            expected_email=email,
            current_password_changed_at=None,
        )
        is None
    )


def test_reset_token_rejected_after_password_change():
    from utils.password_reset import (
        generate_password_reset_token,
        validate_password_reset_token,
    )

    secret = "test-secret"
    email = "user@example.com"

    token = generate_password_reset_token(
        email=email,
        secret=secret,
        expires_in_seconds=60,
        password_changed_at=100.0,
    )

    # user has since changed password
    assert (
        validate_password_reset_token(
            token=token,
            secret=secret,
            expected_email=email,
            current_password_changed_at=200.0,
        )
        is None
    )
