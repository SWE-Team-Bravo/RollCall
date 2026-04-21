from unittest.mock import patch

import pandas as pd

from services.at_risk_cadets import (
    WAIVER_FLAG_THRESHOLD,
    filter_cadets,
    get_df,
    get_waiver_flag_df,
    get_waiver_flagged_cadets,
)

CADET_A = {
    "cadet": {"_id": "1", "first_name": "Tyler", "last_name": "Brooks"},
    "pt_absences": 9,
    "llab_absences": 0,
}
CADET_B = {
    "cadet": {"_id": "2", "first_name": "Nicole", "last_name": "Kim"},
    "pt_absences": 0,
    "llab_absences": 2,
}
CADET_C = {
    "cadet": {"_id": "3", "first_name": "Ashley", "last_name": "Foster"},
    "pt_absences": 5,
    "llab_absences": 1,
}


# ---------------- test filter_cadets ------------------------


def test_filter_cadets_sorted_by_total_descending():
    with patch(
        "services.at_risk_cadets.get_at_risk_cadets",
        return_value=[CADET_B, CADET_C, CADET_A],
    ):
        result = filter_cadets()
        totals = [r["pt_absences"] + r["llab_absences"] for r in result]
        assert totals == sorted(totals, reverse=True)


def test_filter_cadets_returns_all():
    with patch(
        "services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A, CADET_B]
    ):
        result = filter_cadets()
        assert len(result) == 2


def test_filter_cadets_empty():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[]):
        result = filter_cadets()
        assert result == []


def test_filter_cadets_single():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A]):
        result = filter_cadets()
        assert len(result) == 1
        assert result[0]["cadet"]["first_name"] == "Tyler"


# ----------------------- get_df ----------------------------------


def test_get_df_returns_dataframe():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A]):
        result = get_df()
        assert isinstance(result, pd.DataFrame)


def test_get_df_returns_str_if_empty():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[]):
        result = get_df()
        assert isinstance(result, str)


def test_get_df_correct_columns():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A]):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == [
            "No.",
            "First Name",
            "Last Name",
            "PT Absences",
            "LLAB Absences",
        ]


def test_get_df_correct_row_count():
    with patch(
        "services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A, CADET_B]
    ):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2


def test_get_df_numbering_starts_at_one():
    with patch(
        "services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A, CADET_B]
    ):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        assert result["No."].iloc[0] == 1
        assert result["No."].iloc[1] == 2


def test_get_df_contains_cadet_name():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A]):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        assert result["First Name"].iloc[0] == "Tyler"
        assert result["Last Name"].iloc[0] == "Brooks"


def test_get_df_contains_absence_counts():
    with patch("services.at_risk_cadets.get_at_risk_cadets", return_value=[CADET_A]):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        assert result["PT Absences"].iloc[0] == 9
        assert result["LLAB Absences"].iloc[0] == 0


# ----------------------- get_waiver_flagged_cadets ----------------------------------

CADET_DOC = {"_id": "c1", "user_id": "u1", "first_name": "Tyler", "last_name": "Brooks"}
USER_DOC = {"_id": "u1", "first_name": "Tyler", "last_name": "Brooks"}
APPROVED_WAIVER = {"_id": "w1", "status": "approved", "submitted_by_user_id": "u1"}


def test_get_waiver_flagged_cadets_flags_at_threshold():
    waivers = [APPROVED_WAIVER] * WAIVER_FLAG_THRESHOLD
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[CADET_DOC]),
        patch(
            "services.at_risk_cadets.get_approved_waivers_by_user", return_value=waivers
        ),
        patch("services.at_risk_cadets.get_user_by_id", return_value=USER_DOC),
    ):
        result = get_waiver_flagged_cadets()
    assert len(result) == 1
    assert result[0]["waiver_count"] == WAIVER_FLAG_THRESHOLD


def test_get_waiver_flagged_cadets_not_flagged_below_threshold():
    waivers = [APPROVED_WAIVER] * (WAIVER_FLAG_THRESHOLD - 1)
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[CADET_DOC]),
        patch(
            "services.at_risk_cadets.get_approved_waivers_by_user", return_value=waivers
        ),
        patch("services.at_risk_cadets.get_user_by_id", return_value=USER_DOC),
    ):
        result = get_waiver_flagged_cadets()
    assert result == []


def test_get_waiver_flagged_cadets_empty_when_no_cadets():
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[]),
    ):
        result = get_waiver_flagged_cadets()
    assert result == []


def test_get_waiver_flagged_cadets_skips_cadet_without_user_id():
    cadet_no_user = {**CADET_DOC, "user_id": None}
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[cadet_no_user]),
    ):
        result = get_waiver_flagged_cadets()
    assert result == []


def test_get_waiver_flagged_cadets_sorted_most_waivers_first():
    cadet2 = {**CADET_DOC, "_id": "c2", "user_id": "u2"}
    with (
        patch(
            "services.at_risk_cadets.get_all_cadets", return_value=[CADET_DOC, cadet2]
        ),
        patch(
            "services.at_risk_cadets.get_approved_waivers_by_user",
            side_effect=[
                [APPROVED_WAIVER] * 3,
                [APPROVED_WAIVER] * 5,
            ],
        ),
        patch("services.at_risk_cadets.get_user_by_id", return_value=USER_DOC),
    ):
        result = get_waiver_flagged_cadets()
    assert result[0]["waiver_count"] == 5
    assert result[1]["waiver_count"] == 3


def test_get_waiver_flag_df_returns_dataframe():
    waivers = [APPROVED_WAIVER] * WAIVER_FLAG_THRESHOLD
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[CADET_DOC]),
        patch(
            "services.at_risk_cadets.get_approved_waivers_by_user", return_value=waivers
        ),
        patch("services.at_risk_cadets.get_user_by_id", return_value=USER_DOC),
    ):
        result = get_waiver_flag_df()
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == [
        "No.",
        "First Name",
        "Last Name",
        "Approved Waivers",
    ]


def test_get_waiver_flag_df_returns_str_when_empty():
    with (
        patch("services.at_risk_cadets.get_all_cadets", return_value=[]),
    ):
        result = get_waiver_flag_df()
    assert isinstance(result, str)


def test_get_df_sorted_worst_first():
    with patch(
        "services.at_risk_cadets.get_at_risk_cadets",
        return_value=[CADET_B, CADET_C, CADET_A],
    ):
        result = get_df()
        assert isinstance(result, pd.DataFrame)
        pt = list(result["PT Absences"])
        llab = list(result["LLAB Absences"])
        totals = [pt[i] + llab[i] for i in range(len(pt))]
        assert totals == sorted(totals, reverse=True)
