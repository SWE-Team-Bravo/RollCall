import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.db_schema_crud import (
    get_cadet_by_id,
    get_events_by_type,
    get_all_cadets,
    get_attendance_by_cadet,
    get_waivers_by_attendance_records,
    get_flight_by_id,
    get_users_by_role,
    get_cadet_by_user_id,
    get_flight_by_commander,
    set_at_risk_email_sent,
)
from utils.attendance_status import get_effective_attendance_status
from utils.names import format_full_name
from services.event_config import get_absence_thresholds


SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

PT_ABSENCE_THRESHOLD, LLAB_ABSENCE_THRESHOLD = get_absence_thresholds()


def get_at_risk_cadets() -> list[dict]:
    pt_events_ids = {e["_id"] for e in get_events_by_type("pt")}
    llab_events_ids = {e["_id"] for e in get_events_by_type("lab")}

    cadets = get_all_cadets()
    records_by_cadet_id = {
        cadet["_id"]: get_attendance_by_cadet(cadet["_id"]) for cadet in cadets
    }
    all_record_ids = [
        record["_id"]
        for records in records_by_cadet_id.values()
        for record in records
        if record.get("_id") is not None
    ]
    waivers_by_record_id = {
        waiver["attendance_record_id"]: waiver
        for waiver in get_waivers_by_attendance_records(all_record_ids)
        if waiver.get("attendance_record_id") is not None
    }

    at_risk = []
    for cadet in cadets:
        records = records_by_cadet_id[cadet["_id"]]

        pt_absences = sum(
            1
            for r in records
            if get_effective_attendance_status(
                r.get("status"),
                waivers_by_record_id.get(r.get("_id"), {}).get("status"),
            )
            == "absent"
            and r.get("event_id") in pt_events_ids
        )
        llab_absences = sum(
            1
            for r in records
            if get_effective_attendance_status(
                r.get("status"),
                waivers_by_record_id.get(r.get("_id"), {}).get("status"),
            )
            == "absent"
            and r.get("event_id") in llab_events_ids
        )

        if (
            pt_absences >= PT_ABSENCE_THRESHOLD - 1
            or llab_absences >= LLAB_ABSENCE_THRESHOLD - 1
        ):
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
        name = format_full_name(cadet)

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
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = "At-Risk Cadet Absence Report"

    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    table = build_table(cadets)

    body = f"""
    <html><body>
        <p>{greeting}</p>
        <p>The following cadets are one absence away from or have reached the absence thresholds
        (PT: {PT_ABSENCE_THRESHOLD}, LLAB: {LLAB_ABSENCE_THRESHOLD}):</p>
        {table}
        <br>
        <p>RollCall</p>
    </body></html>"""
    msg.attach(MIMEText(body, "html"))
    return msg


def build_email_for_student(
    to_email: str,
    pt_absences: int,
    llab_absences: int,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL or ""
    msg["To"] = to_email
    msg["Subject"] = "At-Risk Alert"

    body = "Hi,\n\n"

    if pt_absences == PT_ABSENCE_THRESHOLD - 1:
        body += (
            f"You're one absence away from reaching the absence threshold for "
            f"PT. Absences: {pt_absences}/{PT_ABSENCE_THRESHOLD}. Contact your cadre immediately."
        )
    elif pt_absences > PT_ABSENCE_THRESHOLD - 1:
        body += (
            f"You have reached the absence threshold for "
            f"PT. Absences: {pt_absences}/{PT_ABSENCE_THRESHOLD}. Contact your cadre immediately."
        )
    if llab_absences == LLAB_ABSENCE_THRESHOLD - 1:
        body += (
            f"You're one absence away from reaching the absence threshold for "
            f"LLAB. Absences: {llab_absences}/{LLAB_ABSENCE_THRESHOLD}. Contact your cadre immediately."
        )
    elif llab_absences > LLAB_ABSENCE_THRESHOLD - 1:
        body += (
            f"You have reached the absence threshold for "
            f"LLAB. Absences: {llab_absences}/{LLAB_ABSENCE_THRESHOLD}. Contact your cadre immediately."
        )

    body += "\n\nRollCall"
    msg.attach(MIMEText(body, "plain"))
    return msg


def send_email(to_email: str, msg: MIMEMultipart) -> bool:
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
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False

    if (
        pt_absences < PT_ABSENCE_THRESHOLD - 1
        and llab_absences < LLAB_ABSENCE_THRESHOLD - 1
    ):
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


def send_to_cadre(at_risk: list[dict], sent, failed) -> tuple[int, int]:
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


def send_to_flight_commander(at_risk: list[dict], sent, failed) -> tuple[int, int]:
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
    at_risk = get_at_risk_cadets()
    if not at_risk:
        return 0, 0

    sent = 0
    failed = 0

    sent, failed = send_to_cadre(at_risk, sent, failed)
    sent, failed = send_to_flight_commander(at_risk, sent, failed)

    return sent, failed
