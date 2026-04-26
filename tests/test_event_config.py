from unittest.mock import patch, MagicMock
from services.event_config import (
    DEFAULT_EMAIL_ENABLED,
    DEFAULT_TIMEZONE,
    get_default_timezone,
    get_event_config,
    save_event_config,
    get_absence_thresholds,
    get_checkin_window_minutes,
    get_waiver_reminder,
    is_email_enabled,
    DEFAULT_PT_THRESHOLD,
    DEFAULT_LLAB_THRESHOLD,
    DEFAULT_CHECKIN_WINDOW_MINUTES,
    DEFAULT_WAIVER_REMINDER_DAYS,
)


# --------------------- test get_event_config --------------------


def test_get_event_config_returns_default_when_db_none():
    with patch("services.event_config.get_db", return_value=None):
        config = get_event_config()
    assert config is not None
    assert config["pt_threshold"] == 9
    assert config["llab_threshold"] == 2
    assert config["checkin_window"] == DEFAULT_CHECKIN_WINDOW_MINUTES
    assert config["waiver_reminder_days"] == 3


def test_get_event_config_returns_existing_doc():
    mock_db = MagicMock()
    mock_db.event_config.find_one.return_value = {
        "pt_threshold": 5,
        "llab_threshold": 1,
    }
    with patch("services.event_config.get_db", return_value=mock_db):
        config = get_event_config()
    assert config is not None
    assert config["pt_threshold"] == 5


def test_get_event_config_creates_default_when_missing():
    mock_db = MagicMock()
    mock_db.event_config.find_one.side_effect = [None, {"pt_threshold": 9}]
    with patch("services.event_config.get_db", return_value=mock_db):
        config = get_event_config()
    mock_db.event_config.insert_one.assert_called_once()
    assert config is not None
    assert config["pt_threshold"] == 9


def test_get_event_config_default_doc_has_all_keys():
    mock_db = MagicMock()
    mock_db.event_config.find_one.side_effect = [
        None,
        {
            "pt_threshold": 9,
            "llab_threshold": 2,
            "checkin_window": 10,
            "waiver_reminder_days": 3,
        },
    ]
    with patch("services.event_config.get_db", return_value=mock_db):
        get_event_config()
    inserted = mock_db.event_config.insert_one.call_args[0][0]
    assert "checkin_window" in inserted
    assert "waiver_reminder_days" in inserted


# --------------------- test save_event_config --------------------


def test_save_event_config_returns_false_when_db_none():
    with patch("services.event_config.get_db", return_value=None):
        result = save_event_config([], [], 9, 2, 10, 3, True)
    assert result is False


def test_save_event_config_calls_update_one():
    mock_db = MagicMock()
    with patch("services.event_config.get_db", return_value=mock_db):
        result = save_event_config(["Monday"], ["Friday"], 5, 1, 15, 7, True)
    assert result is True
    mock_db.event_config.update_one.assert_called_once()
    call_args = mock_db.event_config.update_one.call_args[0][1]["$set"]
    assert call_args["pt_threshold"] == 5
    assert call_args["waiver_reminder_days"] == 7


def test_save_event_config_persists_all_fields():
    mock_db = MagicMock()
    with patch("services.event_config.get_db", return_value=mock_db):
        save_event_config(["Monday"], ["Friday"], 5, 1, 15, 7, False)
    args = mock_db.event_config.update_one.call_args[0][1]["$set"]
    assert args["pt_days"] == ["Monday"]
    assert args["llab_days"] == ["Friday"]
    assert args["llab_threshold"] == 1
    assert args["checkin_window"] == 15
    assert args["email_enabled"] is False


# --------------------- test get_absence_thresholds --------------------


def test_absence_thresholds_from_config():
    with patch(
        "services.event_config.get_event_config",
        return_value={"pt_threshold": 3, "llab_threshold": 1},
    ):
        assert get_absence_thresholds() == (3, 1)


def test_absence_thresholds_defaults_when_none():
    with patch("services.event_config.get_event_config", return_value=None):
        assert get_absence_thresholds() == (
            DEFAULT_PT_THRESHOLD,
            DEFAULT_LLAB_THRESHOLD,
        )


def test_absence_thresholds_defaults_when_keys_missing():
    with patch("services.event_config.get_event_config", return_value={}):
        assert get_absence_thresholds() == (
            DEFAULT_PT_THRESHOLD,
            DEFAULT_LLAB_THRESHOLD,
        )


# --------------------- test get_checkin_window_minutes --------------------


def test_checkin_window_from_config():
    with patch(
        "services.event_config.get_event_config", return_value={"checkin_window": 15}
    ):
        assert get_checkin_window_minutes() == 15


def test_checkin_window_default_when_none():
    with patch("services.event_config.get_event_config", return_value=None):
        assert get_checkin_window_minutes() == DEFAULT_CHECKIN_WINDOW_MINUTES


def test_checkin_window_default_when_key_missing():
    with patch("services.event_config.get_event_config", return_value={}):
        assert get_checkin_window_minutes() == DEFAULT_CHECKIN_WINDOW_MINUTES


# --------------------- test get_waiver_reminder --------------------


def test_waiver_reminder_from_config():
    with patch(
        "services.event_config.get_event_config",
        return_value={"waiver_reminder_days": 7},
    ):
        assert get_waiver_reminder() == 7


def test_waiver_reminder_default_when_none():
    with patch("services.event_config.get_event_config", return_value=None):
        assert get_waiver_reminder() == DEFAULT_WAIVER_REMINDER_DAYS


def test_waiver_reminder_default_when_key_missing():
    with patch("services.event_config.get_event_config", return_value={}):
        assert get_waiver_reminder() == DEFAULT_WAIVER_REMINDER_DAYS


# --------------------- test is_email_enabled --------------------


def test_email_enabled_from_config():
    with patch(
        "services.event_config.get_event_config", return_value={"email_enabled": True}
    ):
        assert is_email_enabled() is True


def test_email_disabled_from_config():
    with patch(
        "services.event_config.get_event_config", return_value={"email_enabled": False}
    ):
        assert is_email_enabled() is False


def test_email_enabled_default_when_none():
    with patch("services.event_config.get_event_config", return_value=None):
        assert is_email_enabled() is DEFAULT_EMAIL_ENABLED


def test_email_enabled_default_when_key_missing():
    with patch("services.event_config.get_event_config", return_value={}):
        assert is_email_enabled() is DEFAULT_EMAIL_ENABLED


# --------------------- test get_default_timezone --------------------


def test_get_default_timezone_returns_configured_value():
    with patch(
        "services.event_config.get_event_config",
        return_value={"default_timezone": "America/Chicago"},
    ):
        assert get_default_timezone() == "America/Chicago"


def test_get_default_timezone_returns_default_when_key_missing():
    with patch("services.event_config.get_event_config", return_value={}):
        assert get_default_timezone() == DEFAULT_TIMEZONE


def test_get_default_timezone_returns_default_when_config_none():
    with patch("services.event_config.get_event_config", return_value=None):
        assert get_default_timezone() == DEFAULT_TIMEZONE


def test_get_default_timezone_returns_default_when_db_none():
    with patch("services.event_config.get_db", return_value=None):
        assert get_default_timezone() == DEFAULT_TIMEZONE


# --------------------- test save_event_config persists default_timezone ------


def test_save_event_config_persists_default_timezone():
    mock_db = MagicMock()
    with patch("services.event_config.get_db", return_value=mock_db):
        save_event_config(
            ["Monday"],
            ["Friday"],
            9,
            2,
            10,
            3,
            True,
            default_timezone="America/Los_Angeles",
        )
    args = mock_db.event_config.update_one.call_args[0][1]["$set"]
    assert args["default_timezone"] == "America/Los_Angeles"


def test_save_event_config_default_timezone_is_eastern_if_omitted():
    mock_db = MagicMock()
    with patch("services.event_config.get_db", return_value=mock_db):
        save_event_config(["Monday"], ["Friday"], 9, 2, 10, 3, True)
    args = mock_db.event_config.update_one.call_args[0][1]["$set"]
    assert args["default_timezone"] == DEFAULT_TIMEZONE
