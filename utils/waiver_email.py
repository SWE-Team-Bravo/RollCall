from datetime import datetime, timezone
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from services.email_templates import get_content, get_email_template
from utils.db_schema_crud import (
    update_waiver,
    get_waiver_by_id,
    get_users_by_role,
)
from services.event_config import is_email_enabled


SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")


def get_cadre_emails() -> list[str]:
    cadre = get_users_by_role("cadre")
    return [u["email"] for u in cadre if u.get("email")]


def build_email(
    to_email: str,
    event_name: str,
    event_date: str,
    status: str,
    comments: str = "",
) -> MIMEMultipart:
    template = get_email_template("waiver_decision")
    comments_text = f"\n\nComments: {comments}" if comments else ""
    subject, body = get_content(
        template,
        status=status.capitalize(),
        event_name=event_name,
        event_date=event_date,
        comments=comments_text,
    )

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    return msg


def build_reminder_email(
    to_email: str,
    waiver_id: str,
    cadet_name: str,
    event_name: str,
    event_date: str,
    days_pending: int,
) -> MIMEMultipart:
    template = get_email_template("waiver_reminder")
    subject, body = get_content(
        template,
        cadet_name=cadet_name,
        event_name=event_name,
        event_date=event_date,
        days_pending=days_pending,
        waiver_id=waiver_id,
    )

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    return msg


def send_waiver_decision_email(
    waiver_id: str,
    to_email: str,
    event_name: str,
    event_date: str,
    status: str,
    comments: str = "",
) -> bool:
    if not is_email_enabled():
        return False
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False

    waiver = get_waiver_by_id(waiver_id)
    if waiver and waiver.get("email_sent"):
        return False

    try:
        msg = build_email(to_email, event_name, event_date, status, comments)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        update_waiver(waiver_id, {"email_sent": True})
        return True
    except Exception:
        logging.exception("Failed to send waiver email to %s", to_email)
        return False


def send_waiver_reminder_email(
    waiver_id: str,
    cadet_name: str,
    event_name: str,
    event_date: str,
    days_pending: int,
) -> bool:
    if not is_email_enabled():
        return False
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False

    cadre_emails = get_cadre_emails()
    if not cadre_emails:
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            for email in cadre_emails:
                msg = build_reminder_email(
                    email, waiver_id, cadet_name, event_name, event_date, days_pending
                )
                server.sendmail(SENDER_EMAIL, email, msg.as_string())

        update_waiver(waiver_id, {"last_reminder_sent_at": datetime.now(timezone.utc)})
        return True
    except Exception:
        logging.exception("Failed to send waiver reminder for waiver %s", waiver_id)
        return False


def send_test_email(to_email: str) -> tuple[bool, str]:
    if not is_email_enabled():
        return False, "Email is disabled."
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False, "Email credentials not configured."

    try:
        template = get_email_template("test_email")
        subject, body = get_content(template)
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        return True, ""
    except smtplib.SMTPAuthenticationError:
        return (
            False,
            "Authentication failed — check EMAIL_ADDRESS and EMAIL_APP_PASSWORD.",
        )
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"
