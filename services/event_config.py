from utils.db import get_db

_DEFAULT_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
_DEFAULT_LLAB_DAYS = ["Friday"]
_DEFAULT_PT_THRESHOLD = 9
_DEFAULT_LLAB_THRESHOLD = 2


def get_event_config() -> dict | None:
    """Return the event schedule config, creating a default one if it doesn't exist."""
    db = get_db()
    if db is None:
        return {
            "pt_days": _DEFAULT_PT_DAYS,
            "llab_days": _DEFAULT_LLAB_DAYS,
            "pt_threshold": _DEFAULT_PT_THRESHOLD,
            "llab_threshold": _DEFAULT_LLAB_THRESHOLD,
        }

    config = db.event_config.find_one({})
    if not config:
        db.event_config.insert_one(
            {
                "pt_days": _DEFAULT_PT_DAYS,
                "llab_days": _DEFAULT_LLAB_DAYS,
                "pt_threshold": _DEFAULT_PT_THRESHOLD,
                "llab_threshold": _DEFAULT_LLAB_THRESHOLD,
            }
        )
        config = db.event_config.find_one({})

    return config or {
        "pt_days": _DEFAULT_PT_DAYS,
        "llab_days": _DEFAULT_LLAB_DAYS,
        "pt_threshold": _DEFAULT_PT_THRESHOLD,
        "llab_threshold": _DEFAULT_LLAB_THRESHOLD,
    }


def save_event_config(
    pt_days: list[str],
    llab_days: list[str],
    pt_threshold: int,
    llab_threshold: int,
) -> bool:
    """Persist updated PT/LLAB day and threshold selections. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    db.event_config.update_one(
        {},
        {
            "$set": {
                "pt_days": pt_days,
                "llab_days": llab_days,
                "pt_threshold": pt_threshold,
                "llab_threshold": llab_threshold,
            }
        },
    )
    return True


_DEFAULT_CHECKIN_WINDOW_MINUTES = 10


def get_checkin_window_minutes() -> int:
    """Return the check-in window duration in minutes, falling back to the default."""
    config = get_event_config()
    if config is None:
        return _DEFAULT_CHECKIN_WINDOW_MINUTES
    return config.get("checkin_window_minutes", _DEFAULT_CHECKIN_WINDOW_MINUTES)


def get_absence_thresholds() -> tuple[int, int]:
    config = get_event_config()
    if config is None:
        return (9, 2)
    return (
        config.get("pt_absence_threshold", 9),
        config.get("llab_absence_threshold", 2),
    )
