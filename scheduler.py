from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta

import streamlit as st

from services.waiver_review import get_waiver_context
from utils.datetime_utils import ensure_utc
from utils.waiver_email import send_waiver_reminder_email
from services.event_config import get_waiver_reminder
from utils.db_schema_crud import get_all_waivers


def send_pending_waiver_reminders_emails():
    n = get_waiver_reminder()
    cutoff = datetime.now(timezone.utc) - timedelta(days=n)

    for w in get_all_waivers():
        if w.get("status") != "pending":
            continue
        created_at = w.get("created_at")
        if not isinstance(created_at, datetime):
            continue
        created_at = ensure_utc(created_at)
        if created_at > cutoff:
            continue
        last_reminder = w.get("last_reminder_sent_at")
        if isinstance(last_reminder, datetime) and ensure_utc(last_reminder) > cutoff:
            continue

        ctx = get_waiver_context(w)
        if ctx is None:
            continue

        send_waiver_reminder_email(
            waiver_id=str(w["_id"]),
            cadet_name=ctx["cadet_name"],
            event_name=ctx["event_name"],
            event_date=ctx["event_date"],
            days_pending=(datetime.now(timezone.utc) - created_at).days,
        )


@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        send_pending_waiver_reminders_emails,
        "cron",
        hour=8,
        timezone="America/New_York",
    )
    scheduler.start()
    return scheduler
