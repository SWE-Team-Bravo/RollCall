from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from services.waivers import (
    get_all_waivers_for_cadet,
    get_absent_records_without_waiver,
    resubmit_auto_denied_waiver,
    withdraw_waiver,
)


# ------------ test get_all_waivers_for_cadet ----------------


def test_get_all_waivers():
    records = [{"_id": "rec1", "event_id": "evt1"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "pending", "reason": "didn't feel like it"}
    }
    events_by_id = {
        "evt1": {
            "_id": "evt1",
            "event_name": "PT Session",
            "start_date": datetime(2026, 3, 10, tzinfo=timezone.utc),
        }
    }

    result = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert len(result) == 1
    assert result[0]["_event_name"] == "PT Session"
    assert result[0]["_event_date"] == "2026-03-10"


def test_skip_records_without_waiver():
    records = [{"_id": "rec1", "event_id": "evt1"}]
    waivers_by_record_id = {}
    events_by_id = {"evt1": {"event_name": "PT", "start_date": None}}

    result = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert result == []


def test_event_missing():
    records = [{"_id": "rec1", "event_id": "evt99"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "pending", "reason": "didn't feel like it"}
    }
    events_by_id = {}

    result = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert result[0]["_event_name"] == "Unknown event"
    assert result[0]["_event_date"] == "Unknown date"


def test_start_date_missing():
    records = [{"_id": "rec1", "event_id": "evt1"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "pending", "reason": "sick"}
    }
    events_by_id = {"evt1": {"event_name": "PT", "start_date": None}}

    result = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert result[0]["_event_name"] == "PT"
    assert result[0]["_event_date"] == "Unknown date"


def test_wont_modify_original_waiver():
    original = {"_id": "w1", "status": "pending", "reason": "didn't feel like it"}
    records = [{"_id": "rec1", "event_id": "evt1"}]
    waivers_by_record_id = {"rec1": original}
    events_by_id = {"evt1": {"event_name": "PT", "start_date": None}}

    get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert "_event_name" not in original
    assert "_event_date" not in original


def test_only_with_waivers():
    records = [
        {"_id": "rec1", "event_id": "evt1"},
        {"_id": "rec2", "event_id": "evt2"},
        {"_id": "rec3", "event_id": "evt3"},
    ]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "pending", "reason": "sick"},
        "rec3": {"_id": "w3", "status": "approved", "reason": "travel"},
    }
    events_by_id = {
        "evt1": {"event_name": "PT", "start_date": None},
        "evt3": {"event_name": "LLAB", "start_date": None},
    }

    result = get_all_waivers_for_cadet(records, waivers_by_record_id, events_by_id)

    assert len(result) == 2
    assert result[0]["_event_name"] == "PT"
    assert result[1]["_event_name"] == "LLAB"


def test_empty_records():
    result = get_all_waivers_for_cadet([], {}, {})
    assert result == []


# ------------ test get_absent_records_without_waiver ----------------


def test_no_waiver_returned():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {}

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert len(result) == 1
    assert result[0]["_id"] == "rec1"


def test_no_present_records():
    records = [
        {"_id": "rec1", "status": "present"},
        {"_id": "rec2", "status": "absent"},
    ]
    waivers_by_record_id = {}

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert len(result) == 1
    assert result[0]["_id"] == "rec2"


def test_no_pending_waivers():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "pending", "auto_denied": False}
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert result == []


def test_no_approved_waivers():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "approved", "auto_denied": False}
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert result == []


def test_no_excused_records():
    records = [
        {"_id": "rec1", "status": "excused"},
        {"_id": "rec2", "status": "absent"},
    ]
    waivers_by_record_id = {}

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert len(result) == 1
    assert result[0]["_id"] == "rec2"


def test_auto_denied_waiver():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "denied", "auto_denied": True}
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert len(result) == 1
    assert result[0]["_id"] == "rec1"


def test_no_manually_denied_waiver():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "denied", "auto_denied": False}
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert result == []


def test_correct_eligibility():
    records = [
        {"_id": "rec1", "status": "absent"},
        {"_id": "rec2", "status": "absent"},
        {"_id": "rec3", "status": "absent"},
        {"_id": "rec4", "status": "present"},
    ]
    waivers_by_record_id = {
        "rec2": {"_id": "w2", "status": "pending", "auto_denied": False},
        "rec3": {"_id": "w3", "status": "denied", "auto_denied": True},
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert result[0]["_id"] == "rec1"
    assert result[1]["_id"] == "rec3"


def test_empty_absent_records():
    result = get_absent_records_without_waiver([], {})
    assert result == []


def test_withdrawn_is_eligible():
    records = [{"_id": "rec1", "status": "absent"}]
    waivers_by_record_id = {
        "rec1": {"_id": "w1", "status": "withdrawn", "auto_denied": False}
    }

    result = get_absent_records_without_waiver(records, waivers_by_record_id)

    assert len(result) == 1
    assert result[0]["_id"] == "rec1"


# ------------ test resubmit_auto_denied_waiver ----------------
def test_still_invalid():
    existing_waiver = {"_id": "w1"}

    with (
        patch(
            "services.waivers.validate_waiver",
            return_value=(False, "Event is not in the current year."),
        ),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        now_pending, why = resubmit_auto_denied_waiver(
            existing_waiver, "rec1", "didn't feel like it"
        )

        assert now_pending is False
        assert why == "Event is not in the current year."

        mock_update.assert_called_once()
        mock_approval.assert_called_once()

        call_kwargs = mock_update.call_args[0][1]
        assert call_kwargs["status"] == "denied"
        assert call_kwargs["auto_denied"] is True


def test_resubmit_valid():
    existing_waiver = {"_id": "w1"}

    with (
        patch("services.waivers.validate_waiver", return_value=(True, "")),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        now_valid, why = resubmit_auto_denied_waiver(
            existing_waiver, "rec1", "didn't feel like it"
        )

        assert now_valid is True
        assert why == ""

        mock_update.assert_called_once()
        mock_approval.assert_called_once()

        call_kwargs = mock_update.call_args[0][1]
        assert call_kwargs["status"] == "pending"
        assert call_kwargs["auto_denied"] is False


def test_approval_has_why_denied_comments():
    existing_waiver = {"_id": "w1"}

    with (
        patch(
            "services.waivers.validate_waiver",
            return_value=(False, "Waivers are not allowed for event type."),
        ),
        patch("services.waivers.update_waiver"),
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        resubmit_auto_denied_waiver(existing_waiver, "rec1", "didn't feel like it")

        comments = mock_approval.call_args[1]["comments"]
        assert "Waivers are not allowed for event type." in comments


def test_saves_new_reason_if_invalid():
    existing_waiver = {"_id": "w1"}

    with (
        patch(
            "services.waivers.validate_waiver",
            return_value=(False, "Waivers are not allowed for event type."),
        ),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval"),
    ):
        resubmit_auto_denied_waiver(existing_waiver, "rec1", "new reason")

        assert mock_update.call_args[0][1]["reason"] == "new reason"


def test_saves_new_reason_if_valid():
    existing_waiver = {"_id": "w1"}

    with (
        patch("services.waivers.validate_waiver", return_value=(True, "")),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval"),
    ):
        resubmit_auto_denied_waiver(existing_waiver, "rec1", "new reason")

        assert mock_update.call_args[0][1]["reason"] == "new reason"


def test_creates_approval_as_pending():
    existing_waiver = {"_id": "w1"}

    with (
        patch("services.waivers.validate_waiver", return_value=(True, "")),
        patch("services.waivers.update_waiver"),
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        resubmit_auto_denied_waiver(existing_waiver, "rec1", "didn't feel like it")

        assert mock_approval.call_args[1]["decision"] == "pending"


# --------------- test withdraw_waiver -------------------


def test_returns_true_on_success():
    mock_result = MagicMock()
    mock_result.modified_count = 1

    with patch("services.waivers.update_waiver", return_value=mock_result):
        assert withdraw_waiver("w1") is True


def test_returns_false_when_not_found():
    mock_result = MagicMock()
    mock_result.modified_count = 0

    with patch("services.waivers.update_waiver", return_value=mock_result):
        assert withdraw_waiver("w1") is False


def test_returns_false_when_update_is_none():
    with patch("services.waivers.update_waiver", return_value=None):
        assert withdraw_waiver("w1") is False
