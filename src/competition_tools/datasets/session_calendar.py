"""Optional exchange schedules; never guess missing exchange sessions."""

import hashlib
import json
from datetime import date, datetime, timedelta
from importlib.metadata import version


def completed_sessions(calendar: str, start: str, end: str, *, as_of: datetime) -> dict:
    if (
        calendar not in {"XNYS", "XHKG"}
        or as_of.tzinfo is None
        or date.fromisoformat(start) > date.fromisoformat(end)
    ):
        raise ValueError("INVALID_CALENDAR_RANGE")
    try:
        import exchange_calendars as xc
        import pandas as pd
    except ImportError:
        raise ValueError("DAILY_DATA_PROFILE_REQUIRED") from None
    try:
        # The dependency requires a nonempty construction interval. Padding
        # permits a one-day holiday or session; only requested dates are used.
        lower = (date.fromisoformat(start) - timedelta(days=7)).isoformat()
        upper = (date.fromisoformat(end) + timedelta(days=7)).isoformat()
        schedule = xc.get_calendar(calendar, start=lower, end=upper).schedule.loc[
            start:end
        ]
        records = [
            (label.date().isoformat(), row["close"].isoformat())
            for label, row in schedule.iterrows()
        ]
        sessions = [
            day for day, close in records if pd.Timestamp(close) <= pd.Timestamp(as_of)
        ]
    except Exception:
        raise ValueError("CALENDAR_UNAVAILABLE") from None
    return {
        "sessions": sessions,
        "calendar_name": calendar,
        "package_version": version("exchange-calendars"),
        "schedule_sha256": hashlib.sha256(
            json.dumps(records, separators=(",", ":")).encode()
        ).hexdigest(),
        "latest_completed_session": sessions[-1] if sessions else None,
    }
