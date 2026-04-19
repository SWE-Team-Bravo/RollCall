from utils.names import format_full_name


def test_format_full_name_returns_trimmed_full_name():
    assert (
        format_full_name({"first_name": " Tyler ", "last_name": " Brooks "})
        == "Tyler Brooks"
    )


def test_format_full_name_handles_missing_last_name():
    assert format_full_name({"first_name": "Tyler"}) == "Tyler"


def test_format_full_name_returns_default_when_name_missing():
    assert format_full_name({"first_name": "", "last_name": ""}, "Unknown") == "Unknown"


def test_format_full_name_returns_default_for_missing_user():
    assert format_full_name(None, "Unknown cadet") == "Unknown cadet"
