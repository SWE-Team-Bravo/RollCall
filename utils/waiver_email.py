import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.db_schema_crud import update_waiver, get_waiver_by_id


SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")


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
        body = (
            f"Your waiver request for {event_name} on {event_date} has been approved."
        )
    elif status == "denied":
        body = f"Your waiver request for {event_name} on {event_date} has been denied."

    if comments:
        body += f"\n\nComments: {comments}"

    body += "\n\nRollCall"
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
        return False
