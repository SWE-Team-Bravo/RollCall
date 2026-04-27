from datetime import date, timedelta

from utils.date_range import expand_event_dates, parse_streamlit_date_range


# =============================================================================
# expand_event_dates
# Week used in tests: Apr 27 (Mon) – May 3 (Sun) 2026
# Default config: PT = Mon/Tue/Thu, LLAB = Fri
# =============================================================================

_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
_LLAB_DAYS = ["Friday"]

_MON = date(2026, 4, 27)
_TUE = date(2026, 4, 28)
_WED = date(2026, 4, 29)
_THU = date(2026, 4, 30)
_FRI = date(2026, 5, 1)
_SAT = date(2026, 5, 2)
_SUN = date(2026, 5, 3)


def test_returns_pt_event_on_monday() -> None:
    result = expand_event_dates(_MON, _MON, _PT_DAYS, _LLAB_DAYS)
    assert len(result) == 1
    assert result[0]["type"] == "PT"


def test_returns_llab_event_on_friday() -> None:
    result = expand_event_dates(_FRI, _FRI, _PT_DAYS, _LLAB_DAYS)
    assert len(result) == 1
    assert result[0]["type"] == "LLAB"


def test_skips_wednesday() -> None:
    assert expand_event_dates(_WED, _WED, _PT_DAYS, _LLAB_DAYS) == []


def test_skips_weekend() -> None:
    assert expand_event_dates(_SAT, _SAT, _PT_DAYS, _LLAB_DAYS) == []
    assert expand_event_dates(_SUN, _SUN, _PT_DAYS, _LLAB_DAYS) == []


def test_full_week_gives_four_events() -> None:
    result = expand_event_dates(_MON, _SUN, _PT_DAYS, _LLAB_DAYS)
    assert len(result) == 4
    pt = [e for e in result if e["type"] == "PT"]
    llab = [e for e in result if e["type"] == "LLAB"]
    assert len(pt) == 3
    assert len(llab) == 1


def test_skip_dates_are_excluded() -> None:
    result = expand_event_dates(_MON, _SUN, _PT_DAYS, _LLAB_DAYS, skip=[_MON, _FRI])
    assert all(e["date"] not in {_MON, _FRI} for e in result)
    assert len(result) == 2


def test_end_before_start_returns_empty() -> None:
    assert expand_event_dates(_FRI, _MON, _PT_DAYS, _LLAB_DAYS) == []


def test_pt_only_when_llab_days_empty() -> None:
    result = expand_event_dates(_MON, _SUN, _PT_DAYS, [])
    assert all(e["type"] == "PT" for e in result)
    assert len(result) == 3


def test_llab_only_when_pt_days_empty() -> None:
    result = expand_event_dates(_MON, _SUN, [], _LLAB_DAYS)
    assert all(e["type"] == "LLAB" for e in result)
    assert len(result) == 1


def test_results_chronologically_ordered() -> None:
    result = expand_event_dates(_MON, _SUN, _PT_DAYS, _LLAB_DAYS)
    dates = [e["date"] for e in result]
    assert dates == sorted(dates)


def test_event_has_day_name() -> None:
    result = expand_event_dates(_MON, _MON, _PT_DAYS, _LLAB_DAYS)
    assert result[0]["day"] == "Monday"


# =============================================================================
# parse_streamlit_date_range
# =============================================================================

_DEFAULT_START = date(2026, 1, 1)
_DEFAULT_END = date(2026, 1, 31)


def test_parses_complete_tuple() -> None:
    start, end, complete = parse_streamlit_date_range(
        (_MON, _FRI), _DEFAULT_START, _DEFAULT_END
    )
    assert (start, end, complete) == (_MON, _FRI, True)


def test_parses_complete_list() -> None:
    start, end, complete = parse_streamlit_date_range(
        [_MON, _FRI], _DEFAULT_START, _DEFAULT_END
    )
    assert (start, end, complete) == (_MON, _FRI, True)


def test_swaps_reversed_tuple() -> None:
    start, end, complete = parse_streamlit_date_range(
        (_FRI, _MON), _DEFAULT_START, _DEFAULT_END
    )
    assert start == _MON
    assert end == _FRI
    assert complete is True


def test_partial_tuple_returns_incomplete() -> None:
    start, end, complete = parse_streamlit_date_range(
        (_MON,), _DEFAULT_START, _DEFAULT_END
    )
    assert start == _MON
    assert end == _DEFAULT_END
    assert complete is False


def test_bare_date_returns_incomplete() -> None:
    start, end, complete = parse_streamlit_date_range(
        _MON, _DEFAULT_START, _DEFAULT_END
    )
    assert start == _MON
    assert end == _DEFAULT_END
    assert complete is False


def test_none_returns_defaults_incomplete() -> None:
    start, end, complete = parse_streamlit_date_range(
        None, _DEFAULT_START, _DEFAULT_END
    )
    assert (start, end, complete) == (_DEFAULT_START, _DEFAULT_END, False)


def test_empty_tuple_returns_defaults_incomplete() -> None:
    start, end, complete = parse_streamlit_date_range((), _DEFAULT_START, _DEFAULT_END)
    assert (start, end, complete) == (_DEFAULT_START, _DEFAULT_END, False)


def test_two_week_range_gives_eight_events() -> None:
    result = expand_event_dates(_MON, _MON + timedelta(days=13), _PT_DAYS, _LLAB_DAYS)
    assert len(result) == 8
