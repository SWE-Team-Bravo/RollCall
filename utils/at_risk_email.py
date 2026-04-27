import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from services.email_templates import get_content, get_email_template
from utils.db_schema_crud import (
    get_cadet_by_id,
    get_all_cadets,
    get_flight_by_id,
    get_users_by_role,
    get_cadet_by_user_id,
    get_flight_by_commander,
    set_at_risk_email_sent,
    get_user_by_id,
    get_cadet_absence_stats,
)
from utils.names import format_full_name
from services.event_config import get_absence_thresholds, is_email_enabled


SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

PT_ABSENCE_THRESHOLD, LLAB_ABSENCE_THRESHOLD = get_absence_thresholds()


def get_at_risk_cadets() -> list[dict]:
    pt_threshold, llab_threshold = get_absence_thresholds()

    stats = {s["cadet_id"]: s for s in get_cadet_absence_stats()}
    cadets = get_all_cadets()

    at_risk = []
    for cadet in cadets:
        s = stats.get(cadet["_id"], {"pt_absences": 0, "llab_absences": 0})
        pt_absences = s["pt_absences"]
        llab_absences = s["llab_absences"]

        if pt_absences >= pt_threshold - 1 or llab_absences >= llab_threshold - 1:
            at_risk.append(
                {
                    "cadet": cadet,
                    "pt_absences": pt_absences,
                    "llab_absences": llab_absences,
                }
            )
    return at_risk


def get_fc_flight_cadets(
    fc: dict, at_risk: list[dict]
) -> tuple[str | None, list[dict]]:
    email = fc.get("email")
    if not email:
        return None, []

    fc_cadet = get_cadet_by_user_id(fc["_id"])
    if fc_cadet is None:
        return None, []

    flight = get_flight_by_commander(fc_cadet["_id"])
    if flight is None:
        return None, []

    flight_cadets = [c for c in at_risk if c["cadet"].get("flight_id") == flight["_id"]]
    return email, flight_cadets


def build_rows(cadets: list[dict]) -> str:
    rows = ""
    for c in cadets:
        cadet = c["cadet"]
        user = None
        user_id = cadet.get("user_id")
        if user_id is not None:
            try:
                user = get_user_by_id(user_id)
            except Exception:
                user = None
        name = format_full_name(user or cadet)

        flight = (
            get_flight_by_id(cadet["flight_id"]) if cadet.get("flight_id") else None
        )
        flight_name = flight.get("name", "Unassigned") if flight else "Unassigned"

        rows += f"""
        <tr>
            <td>{name}</td>
            <td>{flight_name}</td>
            <td>{c["pt_absences"]}</td>
            <td>{c["llab_absences"]}</td>
        </tr>"""
    return rows


def build_table(cadets: list[dict]) -> str:
    rows = build_rows(cadets)
    return f"""
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <thead style="background-color: #f2f2f2;">
            <tr>
                <th> Cadet </th>
                <th> Flight </th>
                <th> PT Absences </th>
                <th> LLAB Absences </th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""


def build_email(
    to_email: str,
    cadets: list[dict],
    recipient_name: str = "",
) -> MIMEMultipart:
    pt_threshold, llab_threshold = get_absence_thresholds()
    template = get_email_template("at_risk_cadre")
    subject, body = get_content(
        template,
        recipient_name=f" {recipient_name}" if recipient_name else "",
        pt_threshold=pt_threshold,
        llab_threshold=llab_threshold,
        table=build_table(cadets),
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    return msg


def build_email_for_student(
    to_email: str,
    pt_absences: int,
    llab_absences: int,
) -> MIMEMultipart:
    pt_threshold, llab_threshold = get_absence_thresholds()
    template = get_email_template("at_risk_student")

    lines = []
    if pt_absences == pt_threshold - 1:
        lines.append(
            f"You're one absence away from reaching the PT threshold. Absences: {pt_absences}/{pt_threshold}. Contact your cadre immediately."
        )
    elif pt_absences > pt_threshold - 1:
        lines.append(
            f"You have reached the PT threshold. Absences: {pt_absences}/{pt_threshold}. Contact your cadre immediately."
        )
    if llab_absences == llab_threshold - 1:
        lines.append(
            f"You're one absence away from reaching the LLAB threshold. Absences: {llab_absences}/{llab_threshold}. Contact your cadre immediately."
        )
    elif llab_absences > llab_threshold - 1:
        lines.append(
            f"You have reached the LLAB threshold. Absences: {llab_absences}/{llab_threshold}. Contact your cadre immediately."
        )

    subject, body = get_content(template, message="\n".join(lines))

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    return msg


def send_email(to_email: str, msg: MIMEMultipart) -> bool:
    if not is_email_enabled():
        return False
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception:
        logging.exception("Failed to send email to %s", to_email)
        return False


def send_to_student(
    cadet_id: str,
    to_email: str,
    pt_absences: int,
    llab_absences: int,
) -> bool:
    if not is_email_enabled():
        return False
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False

    pt_threshold, llab_threshold = get_absence_thresholds()

    if pt_absences < pt_threshold - 1 and llab_absences < llab_threshold - 1:
        return False

    cadet = get_cadet_by_id(cadet_id)
    if cadet:
        last_pt = cadet.get("at_risk_email_last_pt", -1)
        last_llab = cadet.get("at_risk_email_last_llab", -1)
        if last_pt == pt_absences and last_llab == llab_absences:
            return False

    try:
        msg = build_email_for_student(to_email, pt_absences, llab_absences)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        set_at_risk_email_sent(cadet_id, pt_absences, llab_absences)
        return True
    except Exception:
        logging.exception("Failed to send at-risk email to %s", to_email)
        return False


def send_to_cadre(at_risk: list[dict], sent: int, failed: int) -> tuple[int, int]:
    if not is_email_enabled():
        return sent, failed
    for cadre in get_users_by_role("cadre"):
        email = cadre.get("email")
        if not email:
            continue
        msg = build_email(email, at_risk, cadre.get("first_name", ""))
        if send_email(email, msg):
            sent += 1
        else:
            failed += 1
    return sent, failed


def send_to_flight_commander(
    at_risk: list[dict], sent: int, failed: int
) -> tuple[int, int]:
    if not is_email_enabled():
        return sent, failed
    for fc in get_users_by_role("flight_commander"):
        email, flight_cadets = get_fc_flight_cadets(fc, at_risk)
        if not email or not flight_cadets:
            continue
        msg = build_email(email, flight_cadets, fc.get("first_name", ""))
        if send_email(email, msg):
            sent += 1
        else:
            failed += 1
    return sent, failed


def send_at_risk_emails() -> tuple[int, int]:
    if not is_email_enabled():
        return 0, 0
    at_risk = get_at_risk_cadets()
    if not at_risk:
        return 0, 0

    sent = 0
    failed = 0

    sent, failed = send_to_cadre(at_risk, sent, failed)
    sent, failed = send_to_flight_commander(at_risk, sent, failed)

    return sent, failed
