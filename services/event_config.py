from utils.audit_log import log_data_change
from utils.db import get_db

DEFAULT_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
DEFAULT_LLAB_DAYS = ["Friday"]
DEFAULT_PT_THRESHOLD = 9
DEFAULT_LLAB_THRESHOLD = 2
DEFAULT_CHECKIN_WINDOW_MINUTES = 20
DEFAULT_WAIVER_REMINDER_DAYS = 3
DEFAULT_EMAIL_ENABLED = True
DEFAULT_TIMEZONE = "America/New_York"


def get_event_config() -> dict | None:
    """Return the event schedule config, creating a default one if it doesn't exist."""
    db = get_db()
    if db is None:
        return {
            "pt_days": DEFAULT_PT_DAYS,
            "llab_days": DEFAULT_LLAB_DAYS,
            "pt_threshold": DEFAULT_PT_THRESHOLD,
            "llab_threshold": DEFAULT_LLAB_THRESHOLD,
            "checkin_window": DEFAULT_CHECKIN_WINDOW_MINUTES,
            "waiver_reminder_days": DEFAULT_WAIVER_REMINDER_DAYS,
            "email_enabled": DEFAULT_EMAIL_ENABLED,
        }

    config = db.event_config.find_one({})
    if not config:
        db.event_config.insert_one(
            {
                "pt_days": DEFAULT_PT_DAYS,
                "llab_days": DEFAULT_LLAB_DAYS,
                "pt_threshold": DEFAULT_PT_THRESHOLD,
                "llab_threshold": DEFAULT_LLAB_THRESHOLD,
                "checkin_window": DEFAULT_CHECKIN_WINDOW_MINUTES,
                "waiver_reminder_days": DEFAULT_WAIVER_REMINDER_DAYS,
                "email_enabled": DEFAULT_EMAIL_ENABLED,
            }
        )
        config = db.event_config.find_one({})

    return config or {
        "pt_days": DEFAULT_PT_DAYS,
        "llab_days": DEFAULT_LLAB_DAYS,
        "pt_threshold": DEFAULT_PT_THRESHOLD,
        "llab_threshold": DEFAULT_LLAB_THRESHOLD,
        "checkin_window": DEFAULT_CHECKIN_WINDOW_MINUTES,
        "waiver_reminder_days": DEFAULT_WAIVER_REMINDER_DAYS,
        "email_enabled": DEFAULT_EMAIL_ENABLED,
    }


def get_default_timezone() -> str:
    config = get_event_config()
    if config is None:
        return DEFAULT_TIMEZONE
    return config.get("default_timezone", DEFAULT_TIMEZONE)


def save_event_config(
    pt_days: list[str],
    llab_days: list[str],
    pt_threshold: int,
    llab_threshold: int,
    checkin_window: int,
    waiver_reminder_days: int,
    email_enabled: bool,
    default_timezone: str = DEFAULT_TIMEZONE,
    *,
    actor_user_id: str | None = None,
    actor_email: str | None = None,
) -> bool:
    """Persist updated PT/LLAB day and threshold selections, check-in window minutes,
    waiver reminder days, email toggle switch. Returns True on success."""
    db = get_db()
    if db is None:
        return False

    before = db.event_config.find_one({})
    db.event_config.update_one(
        {},
        {
            "$set": {
                "pt_days": pt_days,
                "llab_days": llab_days,
                "pt_threshold": pt_threshold,
                "llab_threshold": llab_threshold,
                "checkin_window": checkin_window,
                "waiver_reminder_days": waiver_reminder_days,
                "email_enabled": email_enabled,
                "default_timezone": default_timezone,
            }
        },
    )
    after = db.event_config.find_one({})

    log_data_change(
        source="event_config",
        action="update",
        target_collection="event_config",
        target_id="global",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_label="Event Schedule Configuration",
        before=dict(before) if before else None,
        after=dict(after) if after else None,
    )

    return True


def get_checkin_window_minutes() -> int:
    """Return the check-in window duration in minutes, falling back to the default."""
    config = get_event_config()
    if config is None:
        return DEFAULT_CHECKIN_WINDOW_MINUTES
    return config.get("checkin_window", DEFAULT_CHECKIN_WINDOW_MINUTES)


def get_absence_thresholds() -> tuple[int, int]:
    config = get_event_config()
    if config is None:
        return (DEFAULT_PT_THRESHOLD, DEFAULT_LLAB_THRESHOLD)
    return (
        config.get("pt_threshold", DEFAULT_PT_THRESHOLD),
        config.get("llab_threshold", DEFAULT_LLAB_THRESHOLD),
    )


def get_waiver_reminder() -> int:
    config = get_event_config()
    if config is None:
        return DEFAULT_WAIVER_REMINDER_DAYS
    return config.get("waiver_reminder_days", DEFAULT_WAIVER_REMINDER_DAYS)


def is_email_enabled() -> bool:
    config = get_event_config()
    if config is None:
        return DEFAULT_EMAIL_ENABLED
    return config.get("email_enabled", DEFAULT_EMAIL_ENABLED)
