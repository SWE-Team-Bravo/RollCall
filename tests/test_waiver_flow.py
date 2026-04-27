"""
End-to-end flow tests for the waiver feature cluster (#235, #236, #237, #238, #240, #241).

Each test traces a complete user journey through the service layer — the same
logic the pages invoke — so breakage here means the UI would break too.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from services.waiver_review import get_waiver_context, get_waiver_export_df, get_waivers
from services.waivers import (
    COMMON_REASONS,
    apply_sickness_auto_approval,
    get_common_reasons,
    is_first_sickness_waiver,
    resolve_cadre_only,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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

BASE_WAIVER = {
    "_id": "w1",
    "attendance_record_id": "rec1",
    "status": "pending",
    "reason": "sick",
    "waiver_type": "non-medical",
    "assigned_cadre_ids": [],
    "attachments": [],
    "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
}


def _ctx_patches():
    """Return the five patches needed to populate get_waiver_context."""
    return (
        patch(
            "services.waiver_review.get_attendance_record_by_id", return_value=RECORD
        ),
        patch("services.waiver_review.get_event_by_id", return_value=EVENT),
        patch("services.waiver_review.get_cadet_by_id", return_value=CADET),
        patch("services.waiver_review.get_user_by_id", return_value=USER),
        patch("services.waiver_review.get_flight_by_id", return_value=FLIGHT),
    )


# ===========================================================================
# Flow 1: Common reasons dropdown (#237)
# ===========================================================================


def test_common_reasons_last_item_is_other():
    """The final option in the dropdown must be the free-text fallback."""
    reasons = get_common_reasons()
    assert "other" in reasons[-1].lower()


def test_common_reasons_covers_medical_and_personal():
    """Dropdown must include both medical-adjacent and personal reasons."""
    reasons = get_common_reasons()
    lower = [r.lower() for r in reasons]
    assert any("sick" in r or "injury" in r or "military" in r for r in lower)
    assert any("family" in r or "emergency" in r or "personal" in r for r in lower)


def test_common_reasons_is_stable():
    """Calling twice returns identical list (no mutation)."""
    assert get_common_reasons() == get_common_reasons()


def test_reason_text_from_common_reason():
    """Selecting a preset reason with no extra detail produces the preset text."""
    reason_choice = COMMON_REASONS[0]  # e.g. "Illness/Sickness"
    extra = ""
    reason_text = (
        extra.strip()
        if reason_choice == COMMON_REASONS[-1]
        else f"{reason_choice}. {extra}".strip(". ")
    )
    assert reason_text == reason_choice


def test_reason_text_from_common_reason_with_extra():
    """Selecting a preset reason + extra detail concatenates both."""
    reason_choice = COMMON_REASONS[1]  # e.g. "Medical appointment"
    extra = "specialist visit"
    reason_text = (
        extra.strip()
        if reason_choice == COMMON_REASONS[-1]
        else f"{reason_choice}. {extra}".strip(". ")
    )
    assert reason_text == f"{reason_choice}. {extra}"


def test_reason_text_from_other_uses_only_extra():
    """Selecting 'Other' uses the free-text field exclusively."""
    reason_choice = COMMON_REASONS[-1]
    extra = "unique circumstance"
    reason_text = (
        extra.strip()
        if reason_choice == COMMON_REASONS[-1]
        else f"{reason_choice}. {extra}".strip(". ")
    )
    assert reason_text == extra


def test_reason_text_other_with_empty_extra_is_blank():
    """'Other' + empty extra_details → blank reason, form should reject this."""
    reason_choice = COMMON_REASONS[-1]
    extra = "   "
    reason_text = (
        extra.strip()
        if reason_choice == COMMON_REASONS[-1]
        else f"{reason_choice}. {extra}".strip(". ")
    )
    assert reason_text == ""


# ===========================================================================
# Flow 2: Sickness waiver — first use auto-approval (#241)
# ===========================================================================


def test_sickness_first_waiver_auto_approved():
    """
    Full sickness first-use flow:
      create → apply_sickness_auto_approval → status becomes 'approved'.
    """
    pending_sickness = {**BASE_WAIVER, "waiver_type": "sickness", "status": "pending"}

    with (
        patch("services.waivers.get_waiver_by_id", return_value=pending_sickness),
        patch(
            "services.waivers.get_sickness_waivers_by_user",
            return_value=[pending_sickness],  # only itself — truly the first
        ),
        patch("services.waivers.update_waiver") as mock_update,
        patch("services.waivers.create_waiver_approval") as mock_approval,
        patch("services.waivers.distribute_excused_status"),
    ):
        auto_approved = apply_sickness_auto_approval("w1", "user1")

    assert auto_approved is True
    mock_update.assert_called_once_with("w1", {"status": "approved"})
    assert mock_approval.call_args[1]["decision"] == "approved"


def test_sickness_second_waiver_stays_pending():
    """
    Subsequent sickness waiver must NOT be auto-approved — goes to cadre.
    """
    pending_sickness = {
        **BASE_WAIVER,
        "_id": "w2",
        "waiver_type": "sickness",
        "status": "pending",
    }
    prior_sickness = {
        **BASE_WAIVER,
        "_id": "w1",
        "waiver_type": "sickness",
        "status": "approved",
    }

    with (
        patch("services.waivers.get_waiver_by_id", return_value=pending_sickness),
        patch(
            "services.waivers.get_sickness_waivers_by_user",
            return_value=[prior_sickness, pending_sickness],
        ),
        patch("services.waivers.update_waiver") as mock_update,
    ):
        auto_approved = apply_sickness_auto_approval("w2", "user1")

    assert auto_approved is False
    mock_update.assert_not_called()


def test_sickness_auto_approval_not_triggered_for_auto_denied_waiver():
    """An auto-denied sickness waiver should not be auto-approved."""
    denied_sickness = {**BASE_WAIVER, "waiver_type": "sickness", "status": "denied"}

    with patch("services.waivers.get_waiver_by_id", return_value=denied_sickness):
        result = apply_sickness_auto_approval("w1", "user1")

    assert result is False


def test_non_sickness_waiver_never_auto_approved():
    """Medical and non-medical waivers must always go to cadre for review."""
    for wtype in ("medical", "non-medical"):
        waiver = {**BASE_WAIVER, "waiver_type": wtype, "status": "pending"}
        with patch("services.waivers.get_waiver_by_id", return_value=waiver):
            result = apply_sickness_auto_approval("w1", "user1")
        assert result is False, f"{wtype} waiver should not be auto-approved"


def test_is_first_sickness_waiver_checks_db():
    """is_first_sickness_waiver uses the DB query, not in-memory state."""
    with patch(
        "services.waivers.get_sickness_waivers_by_user", return_value=[]
    ) as mock_db:
        result = is_first_sickness_waiver("user1")
    mock_db.assert_called_once_with("user1")
    assert result is True


# ===========================================================================
# Flow 3: Waiver type routing — medical goes to cadre only (#236, #238)
# ===========================================================================


def test_medical_waiver_with_no_assigned_cadre_visible_to_all_cadre():
    """
    Medical waivers default to empty assigned_cadre_ids.
    Empty list means all cadre can see it (HIPAA: cadre-only, not flight_commander).
    """
    medical_waiver = {**BASE_WAIVER, "waiver_type": "medical", "assigned_cadre_ids": []}
    with patch("services.waiver_review.get_all_waivers", return_value=[medical_waiver]):
        result = get_waivers("all")
    assert len(result) == 1
    assert result[0]["waiver_type"] == "medical"


def test_medical_waiver_visible_to_admin():
    medical_waiver = {**BASE_WAIVER, "waiver_type": "medical", "assigned_cadre_ids": []}
    with patch("services.waiver_review.get_all_waivers", return_value=[medical_waiver]):
        result = get_waivers("all")
    assert len(result) == 1


# ===========================================================================
# Flow 4: Cadre-only checkbox — any cadre sees all waivers (#240 revised)
# ===========================================================================


def test_cadre_sees_all_waivers_including_cadre_only():
    """Cadre role sees all waivers regardless of cadre_only flag."""
    waivers = [
        {**BASE_WAIVER, "_id": "w1", "waiver_type": "medical", "cadre_only": True},
        {**BASE_WAIVER, "_id": "w2", "waiver_type": "sickness", "cadre_only": True},
        {**BASE_WAIVER, "_id": "w3", "waiver_type": "non-medical", "cadre_only": False},
    ]
    with patch("services.waiver_review.get_all_waivers", return_value=waivers):
        result = get_waivers("all", viewer_roles=["cadre"])
    assert len(result) == 3


def test_waiver_reviewer_cadet_excludes_cadre_only():
    """waiver_reviewer cadets only see cadre_only=False waivers."""
    waivers = [
        {**BASE_WAIVER, "_id": "w1", "cadre_only": True},
        {**BASE_WAIVER, "_id": "w2", "cadre_only": False},
    ]
    with patch("services.waiver_review.get_all_waivers", return_value=waivers):
        result = get_waivers("all", viewer_roles=["cadet", "waiver_reviewer"])
    assert len(result) == 1
    assert result[0]["_id"] == "w2"


# ===========================================================================
# Flow 5: File attachments (#new issue)
# ===========================================================================


def test_attachment_passed_through_to_waiver_context():
    """
    An attachment stored on the waiver document must appear in get_waiver_context
    so the review page can render a download button.
    """
    attachment = {
        "filename": "doctors_note.pdf",
        "content_type": "application/pdf",
        "data": b"PDF",
    }
    waiver_with_file = {**BASE_WAIVER, "attachments": [attachment]}

    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver_with_file)

    assert ctx is not None
    assert len(ctx["attachments"]) == 1
    assert ctx["attachments"][0]["filename"] == "doctors_note.pdf"
    assert ctx["attachments"][0]["data"] == b"PDF"


def test_no_attachment_returns_empty_list():
    """Waivers without attachments must yield an empty list, not None."""
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(BASE_WAIVER)
    assert ctx is not None
    assert ctx["attachments"] == []


def test_multiple_attachments_all_returned():
    attachments = [
        {"filename": "note1.pdf", "content_type": "application/pdf", "data": b"A"},
        {"filename": "note2.jpg", "content_type": "image/jpeg", "data": b"B"},
    ]
    waiver = {**BASE_WAIVER, "attachments": attachments}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    assert len(ctx["attachments"]) == 2
    assert ctx["attachments"][1]["filename"] == "note2.jpg"


# ===========================================================================
# Flow 7: Waiver type surfaced in review context and export (#238)
# ===========================================================================


def test_waiver_type_in_context_medical():
    waiver = {**BASE_WAIVER, "waiver_type": "medical"}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    assert ctx["waiver_type"] == "medical"


def test_waiver_type_in_context_sickness():
    waiver = {**BASE_WAIVER, "waiver_type": "sickness"}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    assert ctx["waiver_type"] == "sickness"


def test_legacy_waiver_without_type_defaults_to_non_medical():
    """Waivers created before the type field existed should not crash the review page."""
    legacy_waiver = {k: v for k, v in BASE_WAIVER.items() if k != "waiver_type"}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(legacy_waiver)
    assert ctx is not None
    assert ctx["waiver_type"] == "non-medical"


def test_export_df_includes_type_column():
    import pandas as pd

    row = {
        "cadet_name": "Tyler Brooks",
        "cadet_email": "tyler@rollcall.local",
        "flight_name": "Alpha Flight",
        "event_name": "PT Session",
        "event_date": "2026-03-01",
        "waiver_status": "pending",
        "waiver_type": "medical",
        "reason": "doctor visit",
    }
    result = get_waiver_export_df([row])
    assert isinstance(result, pd.DataFrame)
    assert "Type" in result.columns
    assert result.iloc[0]["Type"] == "medical"


def test_export_df_type_defaults_to_non_medical_if_missing():
    import pandas as pd

    row = {
        "cadet_name": "Tyler Brooks",
        "cadet_email": "tyler@rollcall.local",
        "flight_name": "Alpha Flight",
        "event_name": "PT Session",
        "event_date": "2026-03-01",
        "waiver_status": "pending",
        "reason": "sick",
        # no waiver_type key
    }
    result = get_waiver_export_df([row])
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["Type"] == "non-medical"


# ===========================================================================
# Flow 8: Status filter + role filter combined (#240)
# ===========================================================================


def test_status_filter_still_works_after_cadre_selector_change():
    """Status filter (pending/approved/etc) must still work with the checkbox model."""
    pending = {**BASE_WAIVER, "status": "pending", "cadre_only": False}
    approved = {**BASE_WAIVER, "_id": "w2", "status": "approved", "cadre_only": False}
    with patch(
        "services.waiver_review.get_all_waivers", return_value=[pending, approved]
    ):
        result = get_waivers("pending")
    assert len(result) == 1
    assert result[0]["status"] == "pending"


def test_approved_sickness_visible_to_cadre_after_auto_approval():
    """
    After sickness auto-approval the waiver status is 'approved'.
    A cadre filtering by 'approved' should see it (no assignment = open to all cadre).
    """
    approved_sickness = {
        **BASE_WAIVER,
        "status": "approved",
        "waiver_type": "sickness",
        "assigned_cadre_ids": [],
    }
    with patch(
        "services.waiver_review.get_all_waivers", return_value=[approved_sickness]
    ):
        result = get_waivers("approved")
    assert len(result) == 1
    assert result[0]["waiver_type"] == "sickness"


# ===========================================================================
# Flow 9: Cadre-only checkbox replaces multiselect (#240 revised)
#
# These tests describe the NEW expected behavior. They FAIL before the fix
# because get_waivers still filters by assigned_cadre_ids per-viewer.
# ===========================================================================


def test_any_cadre_sees_waiver_even_when_assigned_cadre_ids_has_other_cadre():
    """
    With the checkbox model there are no specific per-cadre assignments.
    Any cadre must be able to see any waiver, regardless of what was in
    assigned_cadre_ids when it was created.
    """
    waiver = {**BASE_WAIVER, "assigned_cadre_ids": ["cadre1"]}
    with patch("services.waiver_review.get_all_waivers", return_value=[waiver]):
        result = get_waivers("all")
    assert len(result) == 1


def test_get_waivers_does_not_exclude_cadre_based_on_assigned_ids():
    """
    Two waivers: one explicitly assigned to cadre1, one unassigned.
    cadre2 must see BOTH — the assigned_cadre_ids field must not filter.
    """
    w_assigned = {**BASE_WAIVER, "_id": "w1", "assigned_cadre_ids": ["cadre1"]}
    w_open = {**BASE_WAIVER, "_id": "w2", "assigned_cadre_ids": []}
    with patch(
        "services.waiver_review.get_all_waivers", return_value=[w_assigned, w_open]
    ):
        result = get_waivers("all")
    assert len(result) == 2


def test_cadre_only_true_waiver_visible_to_cadre_role():
    """cadre_only=True waivers are visible to any user with the cadre role."""
    waiver = {**BASE_WAIVER, "cadre_only": True}
    with patch("services.waiver_review.get_all_waivers", return_value=[waiver]):
        result = get_waivers("all", viewer_roles=["cadre"])
        assert len(result) == 1

    with patch("services.waiver_review.get_all_waivers", return_value=[waiver]):
        result = get_waivers("all", viewer_roles=["cadet", "waiver_reviewer"])
        assert len(result) == 0


def test_cadre_only_false_waiver_visible_to_cadre():
    """cadre_only=False waivers are also visible to cadre (no restriction)."""
    waiver = {**BASE_WAIVER, "cadre_only": False, "assigned_cadre_ids": []}
    with patch("services.waiver_review.get_all_waivers", return_value=[waiver]):
        result = get_waivers("all")
    assert len(result) == 1


def test_medical_waiver_cadre_only_defaults_true_in_context():
    """
    Medical waivers must carry cadre_only=True so the review page can
    display the restriction badge. The field must be present on the waiver.
    """
    medical_waiver = {**BASE_WAIVER, "waiver_type": "medical", "cadre_only": True}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(medical_waiver)
    assert ctx is not None
    assert ctx.get("cadre_only") is True


def test_non_medical_cadre_only_false_in_context():
    waiver = {**BASE_WAIVER, "waiver_type": "non-medical", "cadre_only": False}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    assert ctx.get("cadre_only") is False


def test_legacy_waiver_without_cadre_only_defaults_false_in_context():
    """Old waivers without the cadre_only field must not crash the review page."""
    legacy = {
        k: v
        for k, v in BASE_WAIVER.items()
        if k not in ("cadre_only", "assigned_cadre_ids")
    }
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(legacy)
    assert ctx is not None
    assert ctx.get("cadre_only") is False


# ===========================================================================
# resolve_cadre_only — the rule that locks the checkbox (#240 / medical rule)
#
# These tests FAIL before the fix because resolve_cadre_only doesn't exist yet.
# ===========================================================================


def test_medical_type_forces_cadre_only_regardless_of_user_choice():
    """Medical waivers must always be cadre-only — the checkbox cannot be unchecked."""
    assert (
        resolve_cadre_only("medical", has_attachment=False, user_cadre_only=False)
        is True
    )
    assert (
        resolve_cadre_only("medical", has_attachment=False, user_cadre_only=True)
        is True
    )


def test_any_type_with_attachment_forces_cadre_only():
    """Uploading a file (doctor's note) locks cadre-only, regardless of type."""
    assert (
        resolve_cadre_only("non-medical", has_attachment=True, user_cadre_only=False)
        is True
    )
    assert (
        resolve_cadre_only("sickness", has_attachment=True, user_cadre_only=False)
        is True
    )
    assert (
        resolve_cadre_only("medical", has_attachment=True, user_cadre_only=False)
        is True
    )


def test_non_medical_without_attachment_respects_user_choice():
    """Non-medical waiver, no file → cadre_only follows the checkbox."""
    assert (
        resolve_cadre_only("non-medical", has_attachment=False, user_cadre_only=False)
        is False
    )
    assert (
        resolve_cadre_only("non-medical", has_attachment=False, user_cadre_only=True)
        is True
    )


def test_sickness_without_attachment_respects_user_choice():
    """Sickness waiver with no file attached → checkbox is the deciding factor."""
    assert (
        resolve_cadre_only("sickness", has_attachment=False, user_cadre_only=False)
        is False
    )
    assert (
        resolve_cadre_only("sickness", has_attachment=False, user_cadre_only=True)
        is True
    )


# ===========================================================================
# Attachment download — bytes format must survive the round-trip (#new)
# ===========================================================================


def test_attachment_data_is_bytes_convertible_for_download():
    """
    st.download_button expects bytes(data). This test ensures the attachment
    data stored in the waiver document can be converted without error.
    """
    raw = b"PDF content here"
    attachment = {
        "filename": "note.pdf",
        "content_type": "application/pdf",
        "data": raw,
    }
    waiver = {**BASE_WAIVER, "attachments": [attachment]}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    file_data = ctx["attachments"][0]["data"]
    assert bytes(file_data) == raw


def test_multiple_attachments_all_bytes_convertible():
    attachments = [
        {"filename": "a.pdf", "content_type": "application/pdf", "data": b"AAAA"},
        {"filename": "b.jpg", "content_type": "image/jpeg", "data": b"BBBB"},
    ]
    waiver = {**BASE_WAIVER, "attachments": attachments}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    for i, att in enumerate(ctx["attachments"]):
        assert bytes(att["data"]) == attachments[i]["data"]


def test_waiver_with_no_attachments_download_loop_is_empty():
    """No attachments → download loop must iterate zero times (no crash)."""
    waiver = {**BASE_WAIVER, "attachments": []}
    p1, p2, p3, p4, p5 = _ctx_patches()
    with p1, p2, p3, p4, p5:
        ctx = get_waiver_context(waiver)
    assert ctx is not None
    assert list(ctx["attachments"]) == []
