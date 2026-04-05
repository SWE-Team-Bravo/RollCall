from __future__ import annotations

from email.message import Message

from utils.waiver_email import build_email


def _body_from_message(msg: Message) -> str:
    part0 = msg.get_payload(0)
    if isinstance(part0, Message):
        payload = part0.get_payload()
        return payload if isinstance(payload, str) else str(payload)
    return str(part0)


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
