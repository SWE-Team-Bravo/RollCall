from utils.db import get_db


_DEFAULT_TEMPLATES = {
    "waiver_decision": {
        "subject": "Waiver Request {status} — {event_name}",
        "body": "Hi,\n\nYour waiver request for {event_name} on {event_date} has been {status}.{comments}\n\nRollCall",
    },
    "waiver_reminder": {
        "subject": "Pending Waiver Reminder — {cadet_name} — {event_name}",
        "body": "Hi,\n\nA waiver request from {cadet_name} for {event_name} on {event_date} has been pending for {days_pending} day(s) and requires your review.\n\nWaiver ID: {waiver_id}\n\nRollCall",
    },
    "at_risk_cadre": {
        "subject": "At-Risk Cadet Absence Report",
        "body": "Hi{recipient_name},\n\nThe following cadets are approaching or have reached absence thresholds (PT: {pt_threshold}, LLAB: {llab_threshold}):\n\n{table}\n\nRollCall",
    },
    "at_risk_student": {
        "subject": "At-Risk Alert",
        "body": "Hi,\n\n{message}\n\nRollCall",
    },
    "test_email": {
        "subject": "RollCall — Test Email",
        "body": "This is a test email from RollCall. SMTP is configured correctly.",
    },
}


def get_email_template(key: str) -> dict:
    db = get_db()
    if db is not None:
        config = db.event_config.find_one({})
        if config:
            templates = config.get("email_templates", {})
            if key in templates:
                return templates[key]
    return _DEFAULT_TEMPLATES[key]


def get_content(template: dict, **kwargs) -> tuple[str, str]:
    subject = template["subject"].format_map(kwargs)
    body = template["body"].format_map(kwargs)
    return subject, body


def save_email_template(key: str, subject: str, body: str) -> bool:
    db = get_db()
    if db is None:
        return False
    db.event_config.update_one(
        {},
        {"$set": {f"email_templates.{key}": {"subject": subject, "body": body}}},
    )
    return True
