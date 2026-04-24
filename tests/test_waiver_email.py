from __future__ import annotations

from email.message import Message
from unittest.mock import patch

from utils.waiver_email import build_email, build_reminder_email, get_cadre_emails


# ------------------ test build_email ---------------------


def test_subject_approved():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="PT",
        event_date="2026-02-18",
        status="approved",
    )
    assert msg["Subject"] == "Waiver Request Approved — PT"


def test_subject_denied():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="denied",
    )
    assert msg["Subject"] == "Waiver Request Denied — LLAB"


def test_email_recipient():
    msg = build_email(
        to_email="cadet2@rollcall.local",
        event_name="PT",
        event_date="2026-02-18",
        status="approved",
    )
    assert msg["To"] == "cadet2@rollcall.local"


def test_body_approved():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="approved",
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert isinstance(body, str)
    assert "LLAB on 2026-02-18" in body
    assert "approved" in body.lower()


def test_body_denied():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="PT",
        event_date="2026-03-26",
        status="denied",
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert isinstance(body, str)
    assert "PT on 2026-03-26" in body
    assert "denied" in body.lower()


def test_body_comments():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="PT",
        event_date="2026-03-26",
        status="denied",
        comments="Missing documentation.",
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert isinstance(body, str)
    assert "Missing documentation." in body


def test_body_no_comments():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="approved",
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert isinstance(body, str)
    assert "Comments: " not in body


def test_body_signature():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="denied",
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert isinstance(body, str)
    assert "RollCall" in body


# ------------------ test get_cadre_emails ---------------------


def test_get_cadre_emails_returns_emails():
    with patch(
        "utils.waiver_email.get_users_by_role",
        return_value=[
            {"email": "cadre1@rollcall.local"},
            {"email": "cadre2@rollcall.local"},
        ],
    ):
        result = get_cadre_emails()
    assert result == ["cadre1@rollcall.local", "cadre2@rollcall.local"]


def test_get_cadre_emails_skips_missing_email():
    with patch(
        "utils.waiver_email.get_users_by_role",
        return_value=[
            {"email": "cadre1@rollcall.local"},
            {},
        ],
    ):
        result = get_cadre_emails()
    assert result == ["cadre1@rollcall.local"]


def test_get_cadre_emails_empty():
    with patch("utils.waiver_email.get_users_by_role", return_value=[]):
        result = get_cadre_emails()
    assert result == []


# ------------------ test build_reminder_email ---------------------


def test_reminder_subject():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    assert msg["Subject"] == "Pending Waiver Reminder — Tyler Brooks — PT"


def test_reminder_recipient():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    assert msg["To"] == "cadre@rollcall.local"


def test_reminder_body_contains_cadet_name():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert "Tyler Brooks" in body


def test_reminder_body_contains_event_name():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert "PT on 2026-03-01" in body


def test_reminder_body_contains_days_pending():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 5
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert "5 day(s)" in body


def test_reminder_body_contains_waiver_id():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert "w1" in body


def test_reminder_body_signature():
    msg = build_reminder_email(
        "cadre@rollcall.local", "w1", "Tyler Brooks", "PT", "2026-03-01", 3
    )
    part = msg.get_payload(0)
    assert isinstance(part, Message)
    body = part.get_payload()
    assert "RollCall" in body
