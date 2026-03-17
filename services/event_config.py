from utils.db import get_db

_DEFAULT_PT_DAYS = ["Monday", "Tuesday", "Thursday"]
_DEFAULT_LLAB_DAYS = ["Friday"]


def get_event_config() -> dict:
    """Return the event schedule config, creating a default one if it doesn't exist."""
    db = get_db()
    if db is None:
        return {"pt_days": _DEFAULT_PT_DAYS, "llab_days": _DEFAULT_LLAB_DAYS}

    config = db.event_config.find_one({})
    if not config:
        db.event_config.insert_one(
            {
                "pt_days": _DEFAULT_PT_DAYS,
                "llab_days": _DEFAULT_LLAB_DAYS,
            }
        )
        config = db.event_config.find_one({})

    return config or {"pt_days": _DEFAULT_PT_DAYS, "llab_days": _DEFAULT_LLAB_DAYS}


def save_event_config(pt_days: list[str], llab_days: list[str]) -> bool:
    """Persist updated PT/LLAB day selections. Returns True on success."""
    db = get_db()
    if db is None:
        return False
    db.event_config.update_one(
        {},
        {"$set": {"pt_days": pt_days, "llab_days": llab_days}},
    )
    return True
