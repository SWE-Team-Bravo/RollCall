from datetime import datetime, timedelta, timezone

from utils.datetime_utils import ensure_utc


def test_ensure_utc_adds_utc_to_naive_datetime():
    value = datetime(2026, 4, 22, 12, 0, 0)

    result = ensure_utc(value)

    assert result == datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)


def test_ensure_utc_preserves_utc_datetime():
    value = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)

    result = ensure_utc(value)

    assert result == value
    assert result.tzinfo == timezone.utc


def test_ensure_utc_converts_aware_datetime_to_utc():
    eastern = timezone(timedelta(hours=-4))
    value = datetime(2026, 4, 22, 8, 0, 0, tzinfo=eastern)

    result = ensure_utc(value)

    assert result == datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
