from utils.waiver_email import build_email


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
    body = msg.get_payload(0).get_payload()
    assert "LLAB on 2026-02-18" in body
    assert "approved" in body.lower()


def test_body_denied():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="PT",
        event_date="2026-03-26",
        status="denied",
    )
    body = msg.get_payload(0).get_payload()
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
    body = msg.get_payload(0).get_payload()
    assert "Missing documentation." in body


def test_body_no_comments():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="approved",
    )
    body = msg.get_payload(0).get_payload()
    assert "Comments: " not in body


def test_body_signature():
    msg = build_email(
        to_email="cadet1@rollcall.local",
        event_name="LLAB",
        event_date="2026-02-18",
        status="denied",
    )
    body = msg.get_payload(0).get_payload()
    assert "RollCall" in body
