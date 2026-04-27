from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

from bson import ObjectId

from services.waivers import (
    apply_sickness_auto_approval,
    compute_standing_waiver_dates,
    distribute_excused_status,
    get_absent_records_without_waiver,
    get_all_waivers_for_cadet,
    get_common_reasons,
    is_first_sickness_waiver,
    resubmit_auto_denied_waiver,
    revert_excused_status,
    validate_standing_waiver,
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


# --------------- test get_common_reasons -------------------


def test_get_common_reasons_returns_nonempty_list():
    reasons = get_common_reasons()
    assert isinstance(reasons, list)
    assert len(reasons) > 0


def test_get_common_reasons_all_strings():
    reasons = get_common_reasons()
    assert all(isinstance(r, str) for r in reasons)


def test_get_common_reasons_includes_other():
    reasons = get_common_reasons()
    assert any("other" in r.lower() for r in reasons)


# --------------- test is_first_sickness_waiver -------------------


def test_is_first_sickness_waiver_true_when_none_exist():
    with patch("services.waivers.get_sickness_waivers_by_user", return_value=[]):
        assert is_first_sickness_waiver("user1") is True


def test_is_first_sickness_waiver_false_when_existing():
    with patch(
        "services.waivers.get_sickness_waivers_by_user",
        return_value=[{"_id": "w1"}],
    ):
        assert is_first_sickness_waiver("user1") is False


# --------------- test apply_sickness_auto_approval -------------------


def test_apply_sickness_auto_approval_approves_first():
    waiver = {"_id": "w1", "waiver_type": "sickness", "status": "pending"}
    with (
        patch("services.waivers.get_waiver_by_id", return_value=waiver),
        patch(
            "services.waivers.get_sickness_waivers_by_user",
            return_value=[{"_id": "w1"}],
        ),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        result = apply_sickness_auto_approval("w1", "user1")
        assert result is True
        mock_update.assert_called_once()
        mock_approval.assert_called_once()
        assert mock_update.call_args[0][1]["status"] == "approved"


def test_apply_sickness_auto_approval_skips_if_prior_sickness_exists():
    waiver = {"_id": "w1", "waiver_type": "sickness", "status": "pending"}
    with (
        patch("services.waivers.get_waiver_by_id", return_value=waiver),
        patch(
            "services.waivers.get_sickness_waivers_by_user",
            return_value=[{"_id": "w1"}, {"_id": "w2"}],
        ),
        patch("services.waivers.update_waiver") as mock_update,
    ):
        result = apply_sickness_auto_approval("w1", "user1")
        assert result is False
        mock_update.assert_not_called()


def test_apply_sickness_auto_approval_skips_if_not_sickness_type():
    waiver = {"_id": "w1", "waiver_type": "non-medical", "status": "pending"}
    with patch("services.waivers.get_waiver_by_id", return_value=waiver):
        result = apply_sickness_auto_approval("w1", "user1")
        assert result is False


def test_apply_sickness_auto_approval_skips_if_already_denied():
    waiver = {"_id": "w1", "waiver_type": "sickness", "status": "denied"}
    with patch("services.waivers.get_waiver_by_id", return_value=waiver):
        result = apply_sickness_auto_approval("w1", "user1")
        assert result is False


def test_apply_sickness_auto_approval_skips_if_waiver_not_found():
    with patch("services.waivers.get_waiver_by_id", return_value=None):
        result = apply_sickness_auto_approval("w1", "user1")
        assert result is False


def test_apply_sickness_auto_approval_comment_mentions_auto():
    waiver = {"_id": "w1", "waiver_type": "sickness", "status": "pending"}
    with (
        patch("services.waivers.get_waiver_by_id", return_value=waiver),
        patch(
            "services.waivers.get_sickness_waivers_by_user",
            return_value=[{"_id": "w1"}],
        ),
        patch("services.waivers.update_waiver"),
        patch("services.waivers.create_waiver_approval") as mock_approval,
    ):
        apply_sickness_auto_approval("w1", "user1")
        comments = mock_approval.call_args[1]["comments"]
        assert "auto" in comments.lower()


# =============================================================================
# compute_standing_waiver_dates / validate_standing_waiver
# =============================================================================

_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
_LLAB_DAYS = ["Friday"]
_MON = date(2026, 4, 27)
_FRI = date(2026, 5, 1)
_SUN = date(2026, 5, 3)


def _patched_event_config():
    return patch(
        "services.waivers.get_event_config",
        return_value={"pt_days": _PT_DAYS, "llab_days": _LLAB_DAYS},
    )


def test_compute_standing_dates_default_event_types_returns_pt_and_llab():
    with _patched_event_config():
        result = compute_standing_waiver_dates(_MON, _SUN)
    types = {r["type"] for r in result}
    assert types == {"PT", "LLAB"}
    assert len(result) == 4


def test_compute_standing_dates_pt_only():
    with _patched_event_config():
        result = compute_standing_waiver_dates(_MON, _SUN, event_types=["pt"])
    assert all(r["type"] == "PT" for r in result)
    assert len(result) == 3


def test_compute_standing_dates_lab_only():
    with _patched_event_config():
        result = compute_standing_waiver_dates(_MON, _SUN, event_types=["lab"])
    assert all(r["type"] == "LLAB" for r in result)
    assert len(result) == 1


def test_validate_standing_rejects_end_before_start():
    with _patched_event_config():
        ok, why = validate_standing_waiver(_FRI, _MON)
    assert ok is False
    assert "End date" in why


def test_validate_standing_rejects_cross_year():
    with (
        _patched_event_config(),
        patch(
            "services.waivers.datetime",
            wraps=datetime,
        ) as mock_dt,
    ):
        mock_dt.now.return_value = datetime(2026, 6, 1, tzinfo=timezone.utc)
        ok, why = validate_standing_waiver(date(2025, 12, 1), date(2025, 12, 7))
    assert ok is False
    assert "current year" in why


def test_validate_standing_rejects_empty_range_with_no_eligible_days():
    with (
        _patched_event_config(),
        patch(
            "services.waivers.datetime",
            wraps=datetime,
        ) as mock_dt,
    ):
        mock_dt.now.return_value = datetime(2026, 6, 1, tzinfo=timezone.utc)
        ok, why = validate_standing_waiver(date(2026, 5, 2), date(2026, 5, 3))
    assert ok is False
    assert "PT" in why or "LLAB" in why


def test_validate_standing_accepts_valid_range():
    with (
        _patched_event_config(),
        patch(
            "services.waivers.datetime",
            wraps=datetime,
        ) as mock_dt,
    ):
        mock_dt.now.return_value = datetime(2026, 6, 1, tzinfo=timezone.utc)
        ok, why = validate_standing_waiver(_MON, _SUN)
    assert ok is True
    assert why == ""


# =============================================================================
# distribute_excused_status (singular waiver)
# =============================================================================


def test_distribute_singular_flips_absent_to_excused():
    waiver = {
        "_id": "w1",
        "is_standing": False,
        "attendance_record_id": ObjectId("a" * 24),
    }
    record = {
        "_id": ObjectId("a" * 24),
        "cadet_id": ObjectId("b" * 24),
        "event_id": ObjectId("c" * 24),
        "status": "absent",
    }

    with (
        patch("services.waivers.get_attendance_record_by_id", return_value=record),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
        patch("services.waivers.log_attendance_modification") as mock_log,
    ):
        n = distribute_excused_status(waiver, ObjectId("d" * 24))

    assert n == 1
    assert mock_upsert.call_args.kwargs["status"] == "excused"
    assert mock_log.call_args.kwargs["new_status"] == "excused"


def test_distribute_singular_skips_present_record():
    waiver = {
        "_id": "w1",
        "is_standing": False,
        "attendance_record_id": ObjectId("a" * 24),
    }
    record = {
        "_id": ObjectId("a" * 24),
        "cadet_id": ObjectId("b" * 24),
        "event_id": ObjectId("c" * 24),
        "status": "present",
    }

    with (
        patch("services.waivers.get_attendance_record_by_id", return_value=record),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
        patch("services.waivers.log_attendance_modification") as mock_log,
    ):
        n = distribute_excused_status(waiver, ObjectId("d" * 24))

    assert n == 0
    mock_upsert.assert_not_called()
    mock_log.assert_not_called()


def test_distribute_singular_returns_zero_when_record_missing():
    waiver = {
        "_id": "w1",
        "is_standing": False,
        "attendance_record_id": ObjectId("a" * 24),
    }

    with (
        patch("services.waivers.get_attendance_record_by_id", return_value=None),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
    ):
        n = distribute_excused_status(waiver, ObjectId("d" * 24))

    assert n == 0
    mock_upsert.assert_not_called()


# =============================================================================
# distribute_excused_status (standing waiver)
# =============================================================================


def _standing_waiver(event_types=None):
    return {
        "_id": ObjectId("e" * 24),
        "is_standing": True,
        "submitted_by_user_id": ObjectId("f" * 24),
        "start_date": datetime(2026, 4, 27, tzinfo=timezone.utc),
        "end_date": datetime(2026, 5, 3, 23, 59, 59, tzinfo=timezone.utc),
        "event_types": event_types or ["pt", "lab"],
    }


def test_distribute_standing_excuses_all_absent_records_in_range():
    cadet_id = ObjectId("b" * 24)
    cadet = {"_id": cadet_id, "user_id": ObjectId("f" * 24)}
    event_a = {"_id": ObjectId("c" * 24), "event_type": "pt"}
    event_b = {"_id": ObjectId("d" * 24), "event_type": "lab"}
    record_a = {
        "_id": ObjectId("1" * 24),
        "cadet_id": cadet_id,
        "event_id": event_a["_id"],
        "status": "absent",
    }
    record_b = {
        "_id": ObjectId("2" * 24),
        "cadet_id": cadet_id,
        "event_id": event_b["_id"],
        "status": "absent",
    }

    with (
        patch("services.waivers.get_cadet_by_user_id", return_value=cadet),
        patch(
            "services.waivers.get_events_by_date_range",
            return_value=[event_a, event_b],
        ),
        patch(
            "services.waivers.get_attendance_record_by_event_cadet",
            side_effect=[record_a, record_b],
        ),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
        patch("services.waivers.log_attendance_modification"),
    ):
        n = distribute_excused_status(_standing_waiver(), ObjectId("d" * 24))

    assert n == 2
    assert mock_upsert.call_count == 2


def test_distribute_standing_skips_records_already_present():
    cadet_id = ObjectId("b" * 24)
    cadet = {"_id": cadet_id, "user_id": ObjectId("f" * 24)}
    event = {"_id": ObjectId("c" * 24), "event_type": "pt"}
    record = {
        "_id": ObjectId("1" * 24),
        "cadet_id": cadet_id,
        "event_id": event["_id"],
        "status": "present",
    }

    with (
        patch("services.waivers.get_cadet_by_user_id", return_value=cadet),
        patch(
            "services.waivers.get_events_by_date_range",
            return_value=[event],
        ),
        patch(
            "services.waivers.get_attendance_record_by_event_cadet",
            return_value=record,
        ),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
        patch("services.waivers.log_attendance_modification"),
    ):
        n = distribute_excused_status(_standing_waiver(), ObjectId("d" * 24))

    assert n == 0
    mock_upsert.assert_not_called()


def test_distribute_standing_returns_zero_when_no_cadet():
    with (
        patch("services.waivers.get_cadet_by_user_id", return_value=None),
        patch("services.waivers.get_events_by_date_range") as mock_events,
    ):
        n = distribute_excused_status(_standing_waiver(), ObjectId("d" * 24))

    assert n == 0
    mock_events.assert_not_called()


def test_distribute_standing_passes_event_types_filter():
    cadet = {"_id": ObjectId("b" * 24), "user_id": ObjectId("f" * 24)}

    with (
        patch("services.waivers.get_cadet_by_user_id", return_value=cadet),
        patch(
            "services.waivers.get_events_by_date_range", return_value=[]
        ) as mock_events,
        patch("services.waivers.get_attendance_record_by_event_cadet"),
        patch("services.waivers.upsert_attendance_record"),
        patch("services.waivers.log_attendance_modification"),
    ):
        distribute_excused_status(
            _standing_waiver(event_types=["pt"]), ObjectId("d" * 24)
        )

    assert mock_events.call_args.kwargs["event_types"] == ["pt"]


# =============================================================================
# revert_excused_status
# =============================================================================


def test_revert_singular_flips_excused_back_to_absent():
    waiver = {
        "_id": "w1",
        "is_standing": False,
        "attendance_record_id": ObjectId("a" * 24),
    }
    record = {
        "_id": ObjectId("a" * 24),
        "cadet_id": ObjectId("b" * 24),
        "event_id": ObjectId("c" * 24),
        "status": "excused",
    }

    with (
        patch("services.waivers.get_attendance_record_by_id", return_value=record),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
        patch("services.waivers.log_attendance_modification"),
    ):
        n = revert_excused_status(waiver, ObjectId("d" * 24))

    assert n == 1
    assert mock_upsert.call_args.kwargs["status"] == "absent"


def test_revert_singular_leaves_present_alone():
    waiver = {
        "_id": "w1",
        "is_standing": False,
        "attendance_record_id": ObjectId("a" * 24),
    }
    record = {
        "_id": ObjectId("a" * 24),
        "cadet_id": ObjectId("b" * 24),
        "event_id": ObjectId("c" * 24),
        "status": "present",
    }

    with (
        patch("services.waivers.get_attendance_record_by_id", return_value=record),
        patch("services.waivers.upsert_attendance_record") as mock_upsert,
    ):
        n = revert_excused_status(waiver, ObjectId("d" * 24))

    assert n == 0
    mock_upsert.assert_not_called()
