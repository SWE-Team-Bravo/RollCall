from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from services.waiver_review import (
    get_flight_options,
    get_waiver_context,
    get_waiver_export_df,
    get_waivers,
    submit_decision,
)

WAIVER = {
    "_id": "w1",
    "attendance_record_id": "rec1",
    "status": "pending",
    "reason": "sick",
    "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
}
RECORD = {"_id": "rec1", "event_id": "evt1", "cadet_id": "cadet1"}
EVENT = {
    "_id": "evt1",
    "event_name": "PT Session",
    "event_type": "pt",
    "start_date": datetime(2026, 3, 1, tzinfo=timezone.utc),
}
CADET = {"_id": "cadet1", "user_id": "user1", "flight_id": "flight1"}
USER = {
    "_id": "user1",
    "first_name": "Tyler",
    "last_name": "Brooks",
    "email": "tyler@rollcall.local",
}
FLIGHT = {"_id": "flight1", "name": "Alpha Flight"}


# -------------------------- test get_flight_options --------------------------------


def test_get_flight_options_includes_all_flights():
    with patch(
        "services.waiver_review.get_all_flights",
        return_value=[
            {"name": "Alpha Flight"},
            {"name": "Bravo Flight"},
        ],
    ):
        options = get_flight_options()
        assert options[0] == "All flights"
        assert "Alpha Flight" in options
        assert "Bravo Flight" in options


def test_get_flight_options_no_flights():
    with patch("services.waiver_review.get_all_flights", return_value=[]):
        options = get_flight_options()
        assert options == ["All flights"]


def test_get_flight_options_unnamed_flight():
    with patch("services.waiver_review.get_all_flights", return_value=[{}]):
        options = get_flight_options()
        assert "Unnamed flight" in options


# ----------------------- test get_waivers ----------------------------------------


def test_get_waivers_filters_by_status():
    waivers = [
        WAIVER,
        {**WAIVER, "status": "approved"},
        {**WAIVER, "status": "denied"},
    ]
    with patch("services.waiver_review.get_all_waivers", return_value=waivers):
        result = get_waivers("pending")
        assert all(w["status"] == "pending" for w in result)
        assert len(result) == 1


def test_get_waivers_all_returns_everything():
    waivers = [WAIVER, {**WAIVER, "status": "approved"}]
    with patch("services.waiver_review.get_all_waivers", return_value=waivers):
        result = get_waivers("all")
        assert len(result) == 2


def test_get_waivers_sorted_newest_first():
    w1 = {**WAIVER, "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    w2 = {**WAIVER, "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc)}
    with patch("services.waiver_review.get_all_waivers", return_value=[w1, w2]):
        result = get_waivers("all")
        assert result[0]["created_at"] > result[1]["created_at"]


def test_get_waivers_empty():
    with patch("services.waiver_review.get_all_waivers", return_value=[]):
        result = get_waivers("all")
        assert result == []


# ------------------------- test get_waiver_context -----------------------------------------


def test_get_waiver_context_returns_full_context():
    with (
        patch(
            "services.waiver_review.get_attendance_record_by_id", return_value=RECORD
        ),
        patch("services.waiver_review.get_event_by_id", return_value=EVENT),
        patch("services.waiver_review.get_cadet_by_id", return_value=CADET),
        patch("services.waiver_review.get_user_by_id", return_value=USER),
        patch("services.waiver_review.get_flight_by_id", return_value=FLIGHT),
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["cadet_name"] == "Tyler Brooks"
        assert result["cadet_email"] == "tyler@rollcall.local"
        assert result["flight_name"] == "Alpha Flight"
        assert result["event_name"] == "PT Session"
        assert result["event_date"] == "2026-03-01"
        assert result["event_type"] == "pt"


def test_get_waiver_context_returns_none_if_no_record_id():
    result = get_waiver_context({"_id": "w1"})
    assert result is None


def test_get_waiver_context_returns_none_if_record_missing():
    with patch("services.waiver_review.get_attendance_record_by_id", return_value=None):
        result = get_waiver_context(WAIVER)
        assert result is None


def test_get_waiver_context_unknown_cadet_if_user_missing():
    with (
        patch(
            "services.waiver_review.get_attendance_record_by_id", return_value=RECORD
        ),
        patch("services.waiver_review.get_event_by_id", return_value=EVENT),
        patch("services.waiver_review.get_cadet_by_id", return_value=CADET),
        patch("services.waiver_review.get_user_by_id", return_value=None),
        patch("services.waiver_review.get_flight_by_id", return_value=FLIGHT),
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["cadet_name"] == "Unknown cadet"
        assert result["cadet_email"] == ""


def test_get_waiver_context_unassigned_flight_if_no_flight():
    with (
        patch(
            "services.waiver_review.get_attendance_record_by_id", return_value=RECORD
        ),
        patch("services.waiver_review.get_event_by_id", return_value=EVENT),
        patch(
            "services.waiver_review.get_cadet_by_id",
            return_value={**CADET, "flight_id": None},
        ),
        patch("services.waiver_review.get_user_by_id", return_value=USER),
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["flight_name"] == "Unassigned"


def test_get_waiver_context_unknown_event_if_missing():
    with (
        patch(
            "services.waiver_review.get_attendance_record_by_id",
            return_value={**RECORD, "event_id": None},
        ),
        patch("services.waiver_review.get_cadet_by_id", return_value=CADET),
        patch("services.waiver_review.get_user_by_id", return_value=USER),
        patch("services.waiver_review.get_flight_by_id", return_value=FLIGHT),
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["event_name"] == "Unknown event"
        assert result["event_date"] == "Unknown date"


# ------------------------- test submit_decision ----------------------------------


def test_submit_decision_approve():
    with (
        patch("services.waiver_review.update_waiver", return_value=True),
        patch("services.waiver_review.create_waiver_approval", return_value=True),
        patch("services.waiver_review.send_waiver_decision_email"),
    ):
        success, err = submit_decision(
            "w1", "approver1", "Approve", "", "tyler@test.com", "PT", "2026-03-01"
        )
        assert success is True
        assert err == ""


def test_submit_decision_deny():
    with (
        patch("services.waiver_review.update_waiver", return_value=True),
        patch("services.waiver_review.create_waiver_approval", return_value=True),
        patch("services.waiver_review.send_waiver_decision_email"),
    ):
        success, err = submit_decision(
            "w1",
            "approver1",
            "Deny",
            "Not valid.",
            "tyler@test.com",
            "PT",
            "2026-03-01",
        )
        assert success is True
        assert err == ""


def test_submit_decision_fails_if_update_waiver_returns_none():
    with patch("services.waiver_review.update_waiver", return_value=None):
        success, err = submit_decision(
            "w1", "approver1", "Approve", "", "tyler@test.com", "PT", "2026-03-01"
        )
        assert success is False
        assert err != ""


def test_submit_decision_fails_if_create_approval_returns_none():
    with (
        patch("services.waiver_review.update_waiver", return_value=True),
        patch("services.waiver_review.create_waiver_approval", return_value=None),
    ):
        success, err = submit_decision(
            "w1", "approver1", "Approve", "", "tyler@test.com", "PT", "2026-03-01"
        )
        assert success is False
        assert err != ""


def test_submit_decision_sends_email_if_cadet_email_provided():
    with (
        patch("services.waiver_review.update_waiver", return_value=True),
        patch("services.waiver_review.create_waiver_approval", return_value=True),
        patch("services.waiver_review.send_waiver_decision_email") as mock_email,
    ):
        submit_decision(
            "w1", "approver1", "Approve", "", "tyler@test.com", "PT", "2026-03-01"
        )
        mock_email.assert_called_once()


def test_submit_decision_skips_email_if_no_cadet_email():
    with (
        patch("services.waiver_review.update_waiver", return_value=True),
        patch("services.waiver_review.create_waiver_approval", return_value=True),
        patch("services.waiver_review.send_waiver_decision_email") as mock_email,
    ):
        submit_decision("w1", "approver1", "Approve", "", "", "PT", "2026-03-01")
        mock_email.assert_not_called()


# -------------------test get_waiver_export_df ------------------------------------


EXPORT_ROW = {
    "cadet_name": "Tyler Brooks",
    "cadet_email": "tyler@test.com",
    "flight_name": "Alpha Flight",
    "event_name": "PT Session",
    "event_date": "2026-03-01",
    "waiver_status": "pending",
    "reason": "sick",
}


def test_get_waiver_export_df_returns_dataframe():
    result = get_waiver_export_df([EXPORT_ROW])
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert "Cadet" in result.columns


def test_get_waiver_export_df_returns_str_if_empty():
    result = get_waiver_export_df([])
    assert isinstance(result, str)


def test_get_waiver_export_df_correct_columns():
    result = get_waiver_export_df([EXPORT_ROW])
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == [
        "Cadet",
        "Email",
        "Flight",
        "Event",
        "Date",
        "Status",
        "Type",
        "Reason",
    ]


# ----------------------- test get_waivers role filtering -------------------------


def test_get_waivers_all_cadre_see_all_waivers():
    """With checkbox model, any cadre sees any waiver — no per-user ID filtering."""
    w1 = {**WAIVER, "cadre_only": True}
    w2 = {**WAIVER, "_id": "w2", "cadre_only": False}
    with patch("services.waiver_review.get_all_waivers", return_value=[w1, w2]):
        result = get_waivers("all")
        assert len(result) == 2


# ----------------------- test get_waiver_context new fields ----------------------


def _all_patches():
    return (
        patch(
            "services.waiver_review.get_attendance_record_by_id", return_value=RECORD
        ),
        patch("services.waiver_review.get_event_by_id", return_value=EVENT),
        patch("services.waiver_review.get_cadet_by_id", return_value=CADET),
        patch("services.waiver_review.get_user_by_id", return_value=USER),
        patch("services.waiver_review.get_flight_by_id", return_value=FLIGHT),
    )


def test_get_waiver_context_includes_waiver_type():
    waiver_with_type = {**WAIVER, "waiver_type": "medical"}
    with (
        _all_patches()[0],
        _all_patches()[1],
        _all_patches()[2],
        _all_patches()[3],
        _all_patches()[4],
    ):
        result = get_waiver_context(waiver_with_type)
        assert result is not None
        assert result["waiver_type"] == "medical"


def test_get_waiver_context_defaults_waiver_type_to_non_medical():
    with (
        _all_patches()[0],
        _all_patches()[1],
        _all_patches()[2],
        _all_patches()[3],
        _all_patches()[4],
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["waiver_type"] == "non-medical"


def test_get_waiver_context_includes_attachments():
    waiver_with_attachments = {**WAIVER, "attachments": [{"filename": "note.pdf"}]}
    with (
        _all_patches()[0],
        _all_patches()[1],
        _all_patches()[2],
        _all_patches()[3],
        _all_patches()[4],
    ):
        result = get_waiver_context(waiver_with_attachments)
        assert result is not None
        assert result["attachments"] == [{"filename": "note.pdf"}]


def test_get_waiver_context_defaults_attachments_to_empty():
    with (
        _all_patches()[0],
        _all_patches()[1],
        _all_patches()[2],
        _all_patches()[3],
        _all_patches()[4],
    ):
        result = get_waiver_context(WAIVER)
        assert result is not None
        assert result["attachments"] == []
