from datetime import datetime, timezone
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.db_schema_crud import (
    update_waiver,
    get_waiver_by_id,
    get_users_by_role,
)


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
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = f"Waiver Request {status.capitalize()} — {event_name}"

    if status == "approved":
        body = f"Hi,\n\nYour waiver request for {event_name} on {event_date} has been approved."
    elif status == "denied":
        body = f"Hi,\n\nYour waiver request for {event_name} on {event_date} has been denied."

    if comments:
        body += f"\n\nComments: {comments}"

    body += "\n\nRollCall"
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
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = f"Pending Waiver Reminder — {cadet_name} — {event_name}"

    body = (
        f"Hi,\n\n"
        f"A waiver request from {cadet_name} for {event_name} on {event_date} "
        f"has been pending for {days_pending} day(s) and requires your review.\n\n"
        f"Waiver ID: {waiver_id}\n\n"
        f"RollCall"
    )
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
                msg["To"] = email
                server.sendmail(SENDER_EMAIL, email, msg.as_string())

        update_waiver(waiver_id, {"last_reminder_sent_at": datetime.now(timezone.utc)})
        return True
    except Exception:
        logging.exception("Failed to send waiver reminder for waiver %s", waiver_id)
        return False
