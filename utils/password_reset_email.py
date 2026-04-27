from __future__ import annotations

import logging
import os
import smtplib
from urllib.parse import quote
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from services.event_config import is_email_enabled


def _get_sender_credentials() -> tuple[str | None, str | None]:
    sender_email = os.getenv("EMAIL_ADDRESS")
    sender_password = os.getenv("EMAIL_APP_PASSWORD")
    return sender_email, sender_password


def _get_app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "").strip().rstrip("/")


def _send_message(to_email: str, msg: MIMEMultipart) -> bool:
    sender_email, sender_password = _get_sender_credentials()
    if not sender_email or not sender_password:
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except Exception:
        logging.exception("Failed to send email to %s", to_email)
        return False


def send_password_reset_email(*, to_email: str, token: str) -> bool:
    """Send a password reset token to the user's email.

    Link-only: requires APP_BASE_URL to be set so the email contains a clickable link.
    """

    msg = MIMEMultipart("alternative")
    sender_email, _ = _get_sender_credentials()
    msg["From"] = sender_email or ""
    msg["To"] = to_email
    msg["Subject"] = "RollCall Password Reset"

    app_base_url = _get_app_base_url()
    if not app_base_url:
        return False

    reset_link = f"{app_base_url}/?reset_token={quote(token)}&email={quote(to_email)}"
    body = (
        "Hi,\n\n"
        "A password reset was requested for your account. "
        "Use the link below to reset your password (expires soon):\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "RollCall"
    )

    msg.attach(MIMEText(body, "plain"))
    return _send_message(to_email, msg)


def send_temporary_password_email(
    *,
    to_email: str,
    temporary_password: str,
    subject: str | None = None,
    body: str | None = None,
) -> bool:
    if not is_email_enabled():
        return False

    msg = MIMEMultipart("alternative")
    sender_email, _ = _get_sender_credentials()
    msg["From"] = sender_email or ""
    msg["To"] = to_email
    msg["Subject"] = subject or "RollCall Temporary Password"

    email_body = body or (
        "Hi,\n\n"
        "An admin has reset your password. "
        "Use the temporary password below to log in, then change it in Account Settings:\n\n"
        f"{temporary_password}\n\n"
        "RollCall"
    )

    msg.attach(MIMEText(email_body, "plain"))
    return _send_message(to_email, msg)
