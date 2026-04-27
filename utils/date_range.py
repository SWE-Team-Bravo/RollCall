from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def expand_event_dates(
    start: date,
    end: date,
    pt_days: list[str],
    llab_days: list[str],
    skip: Iterable[date] | None = None,
) -> list[dict]:
    """Walk a date range and return event-eligible dates.

    Each entry: {"date": date, "type": "PT"|"LLAB", "day": weekday name}.
    Days that are neither PT nor LLAB, or that appear in `skip`, are omitted.
    """
    if end < start:
        return []
    skip_set = set(skip or [])
    events: list[dict] = []
    current = start
    while current <= end:
        day_name = current.strftime("%A")
        if current not in skip_set:
            if day_name in pt_days:
                events.append({"date": current, "type": "PT", "day": day_name})
            elif day_name in llab_days:
                events.append({"date": current, "type": "LLAB", "day": day_name})
        current += timedelta(days=1)
    return events


def parse_streamlit_date_range(
    value: object,
    default_start: date,
    default_end: date,
) -> tuple[date, date, bool]:
    """Normalize the variable shape returned by st.date_input with a range value.

    Streamlit can return: a tuple/list of 2, a tuple/list of 1 (mid-selection),
    a single bare date, or None. Returns (start, end, is_complete).
    `is_complete` is False when only one endpoint was selected.
    """
    if isinstance(value, (tuple, list)):
        items = tuple(value)
        if len(items) == 2:
            start, end = items
            if isinstance(start, date) and isinstance(end, date):
                if start > end:
                    start, end = end, start
                return start, end, True
        if len(items) == 1 and isinstance(items[0], date):
            return items[0], default_end, False
        return default_start, default_end, False

    if isinstance(value, date):
        return value, default_end, False

    return default_start, default_end, False
