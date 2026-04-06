from datetime import datetime, timedelta, timezone

from services.event_codes import expires_at_from_preset, generate_code


def test_generate_code_is_six_digits():
    code = generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_generate_code_is_zero_padded():
    codes = [generate_code() for _ in range(200)]
    assert all(len(c) == 6 for c in codes)


def test_generate_code_is_numeric_only():
    for _ in range(50):
        assert generate_code().isdigit()


def test_generate_code_produces_varied_results():
    codes = {generate_code() for _ in range(20)}
    assert len(codes) > 1


def test_expires_at_from_preset_15_minutes():
    before = datetime.now(timezone.utc)
    result = expires_at_from_preset("15 minutes")
    after = datetime.now(timezone.utc)
    assert before + timedelta(minutes=14) < result < after + timedelta(minutes=16)


def test_expires_at_from_preset_30_minutes():
    before = datetime.now(timezone.utc)
    result = expires_at_from_preset("30 minutes")
    after = datetime.now(timezone.utc)
    assert before + timedelta(minutes=29) < result < after + timedelta(minutes=31)


def test_expires_at_from_preset_1_hour():
    before = datetime.now(timezone.utc)
    result = expires_at_from_preset("1 hour")
    after = datetime.now(timezone.utc)
    assert before + timedelta(minutes=59) < result < after + timedelta(minutes=61)


def test_expires_at_from_preset_end_of_day():
    result = expires_at_from_preset("end of day")
    assert result.hour == 23
    assert result.minute == 59
    assert result.second == 59


def test_expires_at_from_preset_returns_utc():
    for preset in ("15 minutes", "30 minutes", "1 hour", "end of day"):
        result = expires_at_from_preset(preset)
        assert result.tzinfo == timezone.utc


def test_expires_at_from_preset_is_in_future():
    for preset in ("15 minutes", "30 minutes", "1 hour", "end of day"):
        result = expires_at_from_preset(preset)
        assert result > datetime.now(timezone.utc)
