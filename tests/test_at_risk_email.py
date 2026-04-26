from unittest.mock import MagicMock, patch
from email.mime.text import MIMEText

import pytest

from services.email_templates import _DEFAULT_TEMPLATES
import utils.at_risk_email as m
from utils.at_risk_email import (
    PT_ABSENCE_THRESHOLD,
    LLAB_ABSENCE_THRESHOLD,
    get_at_risk_cadets,
    get_fc_flight_cadets,
    build_rows,
    build_table,
    build_email,
    send_email,
    send_to_cadre,
    send_to_flight_commander,
    send_at_risk_emails,
    build_email_for_student,
    send_to_student,
)


@pytest.fixture(autouse=True)
def mock_templates():
    with patch(
        "utils.waiver_email.get_email_template",
        side_effect=lambda k: _DEFAULT_TEMPLATES[k],
    ):
        yield


def create_cadet(
    first_name="Test",
    last_name="Cadet",
    flight_id="flight1",
    user_id="user_cadet10",
):
    return {
        "_id": "cadet10",
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "flight_id": flight_id,
    }


def make_at_risk(cadet=None, pt=9, llab=0):
    return {
        "cadet": cadet or create_cadet(),
        "pt_absences": pt,
        "llab_absences": llab,
    }


cadet = create_cadet()


# ----------------- test get_at__risk_cadets -------------------


def test_returns_cadet_above_pt_threshold():
    pt_id = "evt_pt"
    records = [{"status": "absent", "event_id": pt_id}] * PT_ABSENCE_THRESHOLD

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
        patch("utils.at_risk_email.get_waivers_by_attendance_records", return_value=[]),
    ):
        result = get_at_risk_cadets()
        assert len(result) == 1
        assert result[0]["pt_absences"] == PT_ABSENCE_THRESHOLD


def test_returns_cadet_above_llab_threshold():
    llab_id = "evt_llab"
    records = [{"status": "absent", "event_id": llab_id}] * LLAB_ABSENCE_THRESHOLD

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": llab_id}] if t == "lab" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
    ):
        result = get_at_risk_cadets()
        assert len(result) == 1
        assert result[0]["llab_absences"] == LLAB_ABSENCE_THRESHOLD


def test_return_only_at_risk_cadets():
    pt_id = "evt_pt"
    safe_cadet = create_cadet(first_name="Safe", last_name="Cadet")
    safe_cadet["_id"] = "safe_cadet"
    at_risk_cadet = create_cadet(first_name="At", last_name="Risk")
    at_risk_cadet["_id"] = "at_risk_cadet"

    attendance = {
        safe_cadet["_id"]: [],
        at_risk_cadet["_id"]: [{"status": "absent", "event_id": pt_id}]
        * PT_ABSENCE_THRESHOLD,
    }

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch(
            "utils.at_risk_email.get_all_cadets",
            return_value=[safe_cadet, at_risk_cadet],
        ),
        patch(
            "utils.at_risk_email.get_attendance_by_cadet",
            side_effect=lambda c_id: attendance[c_id],
        ),
    ):
        result = get_at_risk_cadets()
        assert len(result) == 1
        assert result[0]["cadet"]["first_name"] == "At"


def test_no_cadet_below_thresholds():
    pt_id = "evt_pt"
    records = [{"status": "absent", "event_id": pt_id}] * (PT_ABSENCE_THRESHOLD - 2)

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
    ):
        result = get_at_risk_cadets()
        assert result == []


def test_approved_waiver_absence_does_not_count_for_at_risk():
    pt_id = "evt_pt"
    records = [
        {"_id": f"rec{i}", "status": "absent", "event_id": pt_id}
        for i in range(PT_ABSENCE_THRESHOLD - 1)
    ]
    waivers = [
        {
            "attendance_record_id": records[0]["_id"],
            "status": "approved",
        }
    ]

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
        patch(
            "utils.at_risk_email.get_waivers_by_attendance_records",
            return_value=waivers,
        ),
    ):
        result = get_at_risk_cadets()
        assert result == []


def test_pending_waiver_absence_still_counts_for_at_risk():
    pt_id = "evt_pt"
    records = [
        {"_id": f"rec{i}", "status": "absent", "event_id": pt_id}
        for i in range(PT_ABSENCE_THRESHOLD - 1)
    ]
    waivers = [
        {
            "attendance_record_id": records[0]["_id"],
            "status": "pending",
        }
    ]

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effect=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
        patch(
            "utils.at_risk_email.get_waivers_by_attendance_records",
            return_value=waivers,
        ),
    ):
        result = get_at_risk_cadets()
        assert len(result) == 1
        assert result[0]["pt_absences"] == PT_ABSENCE_THRESHOLD - 1


def test_no_present_records():
    pt_id = "evt_pt"
    records = [{"status": "present", "event_id": pt_id}] * PT_ABSENCE_THRESHOLD

    with (
        patch(
            "utils.at_risk_email.get_events_by_type",
            side_effects=lambda t: [{"_id": pt_id}] if t == "pt" else [],
        ),
        patch("utils.at_risk_email.get_all_cadets", return_value=[cadet]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=records),
    ):
        result = get_at_risk_cadets()
        assert result == []


def test_empty_cadets():
    with (
        patch("utils.at_risk_email.get_events_by_type", return_value=[]),
        patch("utils.at_risk_email.get_all_cadets", return_value=[]),
        patch("utils.at_risk_email.get_attendance_by_cadet", return_value=[]),
    ):
        result = get_at_risk_cadets()
        assert result == []


# ----------------- test get_fc_flight_cadets -------------------


def test_returns_flight_cadets_for_fc():
    fc = {"_id": "user_fc1", "email": "fc1@rollcall.local"}
    fc_cadet = {"_id": "cadet_fc1"}
    flight = {"_id": "flight1"}
    at_risk = [make_at_risk(cadet)]

    with (
        patch("utils.at_risk_email.get_cadet_by_user_id", return_value=fc_cadet),
        patch("utils.at_risk_email.get_flight_by_commander", return_value=flight),
    ):
        email, cadets = get_fc_flight_cadets(fc, at_risk)
        assert email == "fc1@rollcall.local"
        assert len(cadets) == 1


def test_returns_none_email_if_missing():
    fc = {"_id": "user_fc1"}
    email, cadets = get_fc_flight_cadets(fc, [])
    assert email is None
    assert cadets == []


def test_returns_empty_if_fc_cadet_not_found():
    fc = {"_id": "user_fc1", "email": "fc1@rollcall.local"}

    with patch("utils.at_risk_email.get_cadet_by_user_id", return_value=None):
        email, cadets = get_fc_flight_cadets(fc, [])
        assert email is None
        assert cadets == []


def test_returns_empty_if_flight_not_found():
    fc = {"_id": "user_fc1", "email": "fc1@rollcall.local"}
    fc_cadet = {"_id": "cadet_fc1"}

    with (
        patch("utils.at_risk_email.get_cadet_by_user_id", return_value=fc_cadet),
        patch("utils.at_risk_email.get_flight_by_commander", return_value=None),
    ):
        email, cadets = get_fc_flight_cadets(fc, [])
        assert email is None
        assert cadets == []


def test_filters_only_fc_flight_cadets():
    fc = {"_id": "user_fc1", "email": "fc1@rollcall.local"}
    fc_cadet = {"_id": "cadet_fc1"}
    flight = {"_id": "flight1"}
    at_risk = [
        make_at_risk(cadet),
        make_at_risk(create_cadet(flight_id="flight2")),
    ]

    with (
        patch("utils.at_risk_email.get_cadet_by_user_id", return_value=fc_cadet),
        patch("utils.at_risk_email.get_flight_by_commander", return_value=flight),
    ):
        email, cadets = get_fc_flight_cadets(fc, at_risk)
        assert len(cadets) == 1
        assert cadets[0]["cadet"]["flight_id"] == "flight1"


# ----------------- test build_rows -------------------


def test_build_rows_has_cadet_name():
    cadets = [make_at_risk()]

    with (
        patch(
            "utils.at_risk_email.get_flight_by_id",
            return_value={"name": "Alpha Flight"},
        ),
        patch(
            "utils.at_risk_email.get_user_by_id",
            return_value={
                "_id": "user_cadet10",
                "first_name": "Test",
                "last_name": "Cadet",
            },
        ),
    ):
        rows = build_rows(cadets)
        assert "Test Cadet" in rows
        assert "Alpha Flight" in rows


def test_build_rows_unassigned_if_no_flight():
    cadet1 = create_cadet(flight_id=None)
    cadets = [make_at_risk(cadet=cadet1)]

    rows = build_rows(cadets)
    assert "Unassigned" in rows


def test_build_rows_has_absence_counts():
    cadets = [make_at_risk(pt=9, llab=2)]
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        rows = build_rows(cadets)
        assert "9" in rows
        assert "2" in rows


# ----------------- test build_table -------------------


def test_build_table_has_headers():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        table = build_table([make_at_risk()])
        assert "PT Absences" in table
        assert "LLAB Absences" in table
        assert "Cadet" in table
        assert "Flight" in table


# ----------------- test build_email -------------------


def test_build_email_subject():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        msg = build_email("test@rollcall.local", [make_at_risk()], "TJ")
        assert msg["Subject"] == "At-Risk Cadet Absence Report"


def test_build_email_recipient():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        msg = build_email("test@rollcall.local", [make_at_risk()])
        assert msg["To"] == "test@rollcall.local"


def test_build_email_has_greeting():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        msg = build_email("test@rollcall.local", [make_at_risk()], "Charles")
        part = msg.get_payload(0)
        assert isinstance(part, MIMEText)
        body = part.get_payload()
        assert "Hi Charles," in body


def test_build_email_no_greeting():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        msg = build_email("test@rollcall.local", [make_at_risk()])
        part = msg.get_payload(0)
        assert isinstance(part, MIMEText)
        body = part.get_payload()
        assert "Hi," in body


def test_build_email_has_thresholds():
    with patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}):
        msg = build_email("test@rollcall.local", [make_at_risk()])
        part = msg.get_payload(0)
        assert isinstance(part, MIMEText)
        body = part.get_payload()
        assert str(PT_ABSENCE_THRESHOLD) in body
        assert str(LLAB_ABSENCE_THRESHOLD) in body


# ----------------- test send_email ----------------------


def test_send_email_false_if_no_credentials():
    original = m.SENDER_EMAIL
    m.SENDER_EMAIL = None
    result = send_email("test@rollcall.local", MagicMock())
    m.SENDER_EMAIL = original
    assert result is False


def test_send_email_false_on_exception():
    with patch(
        "utils.at_risk_email.smtplib.SMTP_SSL",
        side_effect=Exception("Connection Failed"),
    ):
        result = send_email("test@rollcall.local", MagicMock())
        assert result is False


def test_send_email_returns_true_on_success():
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", "test@gmail.com"),
        patch("utils.at_risk_email.SENDER_PASSWORD", "testpassword"),
        patch("utils.at_risk_email.smtplib.SMTP_SSL") as mock_smtp,
    ):
        mock_smtp.return_value.__enter__.return_value = MagicMock()
        mock_smtp.return_value.__exit__.return_value = False
        result = send_email("test@rollcall.local", MagicMock())
        assert result is True


# ----------------- test send_to_cadre -------------------


def test_send_to_cadre_success():
    at_risk = [make_at_risk()]
    cadre = [{"email": "cadre@rollcall.local", "first_name": "Cadre"}]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=cadre),
        patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}),
        patch("utils.at_risk_email.send_email", return_value=True),
    ):
        sent, failed = send_to_cadre(at_risk, 0, 0)
        assert sent == 1
        assert failed == 0


def test_send_to_cadre_failure():
    at_risk = [make_at_risk()]
    cadre = [{"email": "cadre@rollcall.local", "first_name": "Cadre"}]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=cadre),
        patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}),
        patch("utils.at_risk_email.send_email", return_value=False),
    ):
        sent, failed = send_to_cadre(at_risk, 0, 0)
        assert sent == 0
        assert failed == 1


def test_send_to_cadre_skips_missing_email():
    at_risk = [make_at_risk()]
    cadre = [{"first_name": "Cadre"}]

    with patch("utils.at_risk_email.get_users_by_role", return_value=cadre):
        sent, failed = send_to_cadre(at_risk, 0, 0)
        assert sent == 0
        assert failed == 0


# ----------------- test send_to_flight_commander -------------------


def test_send_to_flight_commander_success():
    at_risk = [make_at_risk(cadet=cadet)]
    fc = [{"_id": "user_fc1", "email": "fc1@rollcall.local", "first_name": "Brent"}]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=fc),
        patch(
            "utils.at_risk_email.get_fc_flight_cadets",
            return_value=("fc1@rollcall.local", at_risk),
        ),
        patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}),
        patch("utils.at_risk_email.send_email", return_value=True),
    ):
        sent, failed = send_to_flight_commander(at_risk, 0, 0)
        assert sent == 1
        assert failed == 0


def test_send_to_flight_commander_failure():
    at_risk = [make_at_risk(cadet=cadet)]
    fc = [{"_id": "user_fc1", "email": "fc1@rollcall.local", "first_name": "Elijah"}]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=fc),
        patch(
            "utils.at_risk_email.get_fc_flight_cadets",
            return_value=("fc1@rollcall.local", at_risk),
        ),
        patch("utils.at_risk_email.get_flight_by_id", return_value={"name": "Alpha"}),
        patch("utils.at_risk_email.send_email", return_value=False),
    ):
        sent, failed = send_to_flight_commander(at_risk, 0, 0)
        assert sent == 0
        assert failed == 1


def test_send_to_flight_commander_skip_no_flight_cadets():
    at_risk = [make_at_risk()]
    fc = [{"_id": "user_fc1", "email": "fc1@rollcall.local", "first_name": "Koussay"}]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=fc),
        patch("utils.at_risk_email.get_fc_flight_cadets", return_value=(None, [])),
    ):
        sent, failed = send_to_flight_commander(at_risk, 0, 0)
        assert sent == 0
        assert failed == 0


def test_send_to_flight_commander_skips_missing_email():
    at_risk = [make_at_risk()]
    fc = [
        {"_id": "user_fc1", "email": "fc1@rollcall.local", "first_name": "Priyadharsan"}
    ]

    with (
        patch("utils.at_risk_email.get_users_by_role", return_value=fc),
        patch("utils.at_risk_email.get_fc_flight_cadets", return_value=(None, at_risk)),
    ):
        sent, failed = send_to_flight_commander(at_risk, 0, 0)
        assert sent == 0
        assert failed == 0


# ----------------- test send_at_risk_emails -------------------


def test_send_at_risk_emails_no_at_risk():
    with patch("utils.at_risk_email.get_at_risk_cadets", return_value=[]):
        sent, failed = send_at_risk_emails()
        assert sent == 0
        assert failed == 0


def test_send_at_risk_emails_call_both_functions():
    at_risk = [make_at_risk()]

    with (
        patch("utils.at_risk_email.get_at_risk_cadets", return_value=at_risk),
        patch("utils.at_risk_email.send_to_cadre", return_value=(1, 0)) as mock_cadre,
        patch(
            "utils.at_risk_email.send_to_flight_commander", return_value=(2, 0)
        ) as mock_fc,
    ):
        sent, failed = send_at_risk_emails()
        assert sent == 2
        assert failed == 0
        mock_cadre.assert_called_once()
        mock_fc.assert_called_once()


# ----------------- test build_email_for_student -------------------


def test_build_email_for_student_subject():
    msg = build_email_for_student("cadet@rollcall.local", 8, 0)
    assert msg["Subject"] == "At-Risk Alert"


def test_build_email_for_students_recipient():
    msg = build_email_for_student("cadet@rollcall.local", 8, 0)
    assert msg["To"] == "cadet@rollcall.local"


def test_build_email_for_student_pt_warning():
    msg = build_email_for_student("cadet@rollcall.local", PT_ABSENCE_THRESHOLD - 1, 0)
    part = msg.get_payload(0)
    assert isinstance(part, MIMEText)
    body = part.get_payload()
    assert "one absence away" in body
    assert "PT" in body


def test_build_email_for_student_pt_exceeded():
    msg = build_email_for_student("cadet@rollcall.local", PT_ABSENCE_THRESHOLD, 0)
    part = msg.get_payload(0)
    assert isinstance(part, MIMEText)
    body = part.get_payload()
    assert "reached" in body
    assert "PT" in body


def test_build_email_for_student_llab_warning():
    msg = build_email_for_student("cadet@rollcall.local", 0, LLAB_ABSENCE_THRESHOLD - 1)
    part = msg.get_payload(0)
    assert isinstance(part, MIMEText)
    body = part.get_payload()
    assert "one absence away" in body
    assert "LLAB" in body


def test_build_email_for_student_llab_exceeded():
    msg = build_email_for_student("cadet@rollcall.local", 0, LLAB_ABSENCE_THRESHOLD)
    part = msg.get_payload(0)
    assert isinstance(part, MIMEText)
    body = part.get_payload()
    assert "reached" in body
    assert "LLAB" in body


def test_build_email_for_student_signature():
    msg = build_email_for_student("cadet@rollcall.local", 8, 0)
    part = msg.get_payload(0)
    assert isinstance(part, MIMEText)
    body = part.get_payload()
    assert "RollCall" in body


# ----------------- test send_to_student -------------------


def test_send_to_student_returns_false_no_credentials():
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", None),
        patch("utils.at_risk_email.get_cadet_by_id", return_value={}),
    ):
        result = send_to_student("c1", "cadet@rollcall.local", 8, 0)
        assert result is False


def test_send_to_student_returns_false_below_threshhold():
    result = send_to_student("c1", "cadet@rollcall.local", 0, 0)
    assert result is False


def test_send_to_student_no_resend_counts_unchanged():
    cadet = {"_id": "c1", "at_risk_email_last_pt": 8, "at_risk_email_last_llab": 0}
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", "test@gmail.com"),
        patch("utils.at_risk_email.SENDER_PASSWORD", "testpassword"),
        patch("utils.at_risk_email.get_cadet_by_id", return_value=cadet),
    ):
        result = send_to_student("c1", "cadet@rollcall.local", 8, 0)
        assert result is False


def test_send_to_student_sends_if_counts_increased():
    cadet = {"_id": "c1", "at_risk_email_last_pt": 8, "at_risk_email_last_llab": 0}
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", "test@gmail.com"),
        patch("utils.at_risk_email.SENDER_PASSWORD", "testpassword"),
        patch("utils.at_risk_email.get_cadet_by_id", return_value=cadet),
        patch("utils.at_risk_email.set_at_risk_email_sent"),
        patch("utils.at_risk_email.smtplib.SMTP_SSL") as mock_smtp,
    ):
        mock_smtp.return_value.__enter__.return_value = MagicMock()
        mock_smtp.return_value.__exit__.return_value = False
        result = send_to_student("c1", "cadet@rollcall.local", 9, 0)
        assert result is True


def test_send_to_student_sends_if_no_previous_record():
    cadet = {"_id": "c1"}
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", "test@gmail.com"),
        patch("utils.at_risk_email.SENDER_PASSWORD", "testpassword"),
        patch("utils.at_risk_email.get_cadet_by_id", return_value=cadet),
        patch("utils.at_risk_email.set_at_risk_email_sent"),
        patch("utils.at_risk_email.smtplib.SMTP_SSL") as mock_smtp,
    ):
        mock_smtp.return_value.__enter__.return_value = MagicMock()
        mock_smtp.return_value.__exit__.return_value = False
        result = send_to_student("c1", "cadet@rollcall.local", 8, 0)
        assert result is True


def test_send_to_student_returns_false_on_exception():
    cadet = {"_id": "c1"}
    with (
        patch("utils.at_risk_email.SENDER_EMAIL", "test@gmail.com"),
        patch("utils.at_risk_email.SENDER_PASSWORD", "testpassword"),
        patch("utils.at_risk_email.get_cadet_by_id", return_value=cadet),
        patch("utils.at_risk_email.smtplib.SMTP_SSL", side_effect=Exception("fail")),
    ):
        result = send_to_student("c1", "cadet@rollcall.local", 8, 0)
        assert result is False


def test_send_email_returns_false_when_email_disabled():
    with patch("utils.at_risk_email.is_email_enabled", return_value=False):
        result = send_email("test@rollcall.local", MagicMock())
    assert result is False


def test_send_to_cadre_returns_unchanged_counts_when_email_disabled():
    with patch("utils.at_risk_email.is_email_enabled", return_value=False):
        sent, failed = send_to_cadre([make_at_risk()], 0, 0)
    assert sent == 0
    assert failed == 0


def test_send_to_flight_commander_returns_unchanged_counts_when_email_disabled():
    with patch("utils.at_risk_email.is_email_enabled", return_value=False):
        sent, failed = send_to_flight_commander([make_at_risk()], 0, 0)
    assert sent == 0
    assert failed == 0


def test_send_at_risk_emails_returns_zeros_when_email_disabled():
    with patch("utils.at_risk_email.is_email_enabled", return_value=False):
        sent, failed = send_at_risk_emails()
    assert sent == 0
    assert failed == 0


def test_send_to_student_returns_false_when_email_disabled():
    with patch("utils.at_risk_email.is_email_enabled", return_value=False):
        result = send_to_student("c1", "cadet@rollcall.local", 8, 0)
    assert result is False
