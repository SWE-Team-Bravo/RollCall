import smtplib
from unittest.mock import MagicMock, patch

from utils.password_reset_email import (
    send_temporary_password_email,
)


def test_returns_false_when_email_disabled():
    with patch("utils.password_reset_email.is_email_enabled", return_value=False):
        result = send_temporary_password_email(
            to_email="user@example.com", temporary_password="abc123"
        )
    assert result is False


def test_uses_custom_subject_and_body():
    mock_server = MagicMock()
    with (
        patch("utils.password_reset_email.is_email_enabled", return_value=True),
        patch(
            "utils.password_reset_email._get_sender_credentials",
            return_value=("sender@example.com", "password"),
        ),
        patch(
            "utils.password_reset_email.smtplib.SMTP_SSL",
            return_value=MagicMock(
                __enter__=lambda s, *a: mock_server,
                __exit__=MagicMock(return_value=False),
            ),
        ),
    ):
        result = send_temporary_password_email(
            to_email="user@example.com",
            temporary_password="abc123",
            subject="Custom Subject",
            body="Custom Body abc123",
        )
    assert result is True
    sent_msg = mock_server.sendmail.call_args[0][2]
    assert "Custom Subject" in sent_msg
    assert "Custom Body abc123" in sent_msg


def test_falls_back_to_defaults_when_subject_and_body_omitted():
    mock_server = MagicMock()
    with (
        patch("utils.password_reset_email.is_email_enabled", return_value=True),
        patch(
            "utils.password_reset_email._get_sender_credentials",
            return_value=("sender@example.com", "password"),
        ),
        patch(
            "utils.password_reset_email.smtplib.SMTP_SSL",
            return_value=MagicMock(
                __enter__=lambda s, *a: mock_server,
                __exit__=MagicMock(return_value=False),
            ),
        ),
    ):
        result = send_temporary_password_email(
            to_email="user@example.com",
            temporary_password="abc123",
        )
    assert result is True
    sent_msg = mock_server.sendmail.call_args[0][2]
    assert "RollCall Temporary Password" in sent_msg
    assert "abc123" in sent_msg


def test_returns_false_when_credentials_missing():
    with (
        patch("utils.password_reset_email.is_email_enabled", return_value=True),
        patch(
            "utils.password_reset_email._get_sender_credentials",
            return_value=(None, None),
        ),
    ):
        result = send_temporary_password_email(
            to_email="user@example.com", temporary_password="abc123"
        )
    assert result is False


def test_returns_false_on_smtp_exception():
    with (
        patch("utils.password_reset_email.is_email_enabled", return_value=True),
        patch(
            "utils.password_reset_email._get_sender_credentials",
            return_value=("sender@example.com", "password"),
        ),
        patch(
            "utils.password_reset_email.smtplib.SMTP_SSL",
            side_effect=smtplib.SMTPException("connection failed"),
        ),
    ):
        result = send_temporary_password_email(
            to_email="user@example.com", temporary_password="abc123"
        )
    assert result is False
