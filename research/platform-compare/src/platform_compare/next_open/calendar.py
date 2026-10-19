"""Versioned exchange-session clock derivation for the next-open study."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from exchange_calendars import ExchangeCalendar

MARKET_CALENDARS: Mapping[str, str] = {
    "US": "XNYS",
    "HK": "XHKG",
    "UK": "XLON",
    "AU": "XASX",
    "SG": "XSES",
}
CALENDAR_PACKAGE = "exchange_calendars"
CALENDAR_PACKAGE_VERSION = "4.13.2"
CalendarSet = Mapping[str, ExchangeCalendar]


@dataclass(frozen=True, slots=True)
class ScheduledSession:
    market: str
    session_date: date
    scheduled_open_at: datetime
    scheduled_close_at: datetime


def _session_date(value: date) -> date:
    if type(value) is not date:
        raise ValueError("session date must be a plain date")
    return value


def _scheduled_session(
    market: str, session: date, calendars: CalendarSet
) -> ScheduledSession:
    if market not in MARKET_CALENDARS or market not in calendars:
        raise ValueError(f"unsupported market calendar: {market}")
    calendar = calendars[market]
    label = pd.Timestamp(session.isoformat())
    if not calendar.is_session(label):
        raise ValueError(
            f"{session.isoformat()} is not a scheduled {market} source session"
        )
    opened = calendar.session_open(label).tz_convert("UTC").to_pydatetime()
    closed = calendar.session_close(label).tz_convert("UTC").to_pydatetime()
    return ScheduledSession(market, session, opened, closed)


def derive_signal_clock(
    signal_date: date,
    source_sessions: Mapping[str, date],
    calendars: CalendarSet,
) -> datetime:
    """Use the latest scheduled UTC close among the signal's source sessions."""
    signal_date = _session_date(signal_date)
    if not source_sessions:
        raise ValueError("signal must have at least one source session")
    closes: list[datetime] = []
    for market, source_date in source_sessions.items():
        source_date = _session_date(source_date)
        if source_date > signal_date:
            raise ValueError("source session is after signal date")
        closes.append(
            _scheduled_session(market, source_date, calendars).scheduled_close_at
        )
    return max(closes)


def first_open_after(
    market: str,
    decision_at: datetime,
    available_sessions: Sequence[date],
    calendars: CalendarSet,
) -> ScheduledSession:
    """Find the first scheduled market open after the global signal clock.

    The selected session must have a source bar. If the first later exchange
    session is missing from ``available_sessions``, fail rather than skipping
    to a later bar.
    """
    if market not in MARKET_CALENDARS or market not in calendars:
        raise ValueError(f"unsupported market calendar: {market}")
    if not isinstance(decision_at, datetime) or decision_at.tzinfo is None:
        raise ValueError("decision timestamp must be timezone-aware UTC")
    if decision_at.utcoffset() != timedelta(0):
        raise ValueError("decision timestamp must be timezone-aware UTC")
    dates = tuple(_session_date(value) for value in available_sessions)
    if len(dates) != len(set(dates)):
        raise ValueError("source sessions contain duplicate dates")
    if not dates:
        raise ValueError("no source sessions available")

    calendar = calendars[market]
    first_label = pd.Timestamp((decision_at.date() - timedelta(days=2)).isoformat())
    last_label = pd.Timestamp(max(dates).isoformat())
    if last_label < first_label:
        raise ValueError("no source session after decision timestamp")
    sessions = calendar.sessions_in_range(first_label, last_label)
    available = set(dates)
    for label in sessions:
        session_date = label.date()
        opened = calendar.session_open(label).tz_convert("UTC").to_pydatetime()
        if opened <= decision_at:
            continue
        if session_date not in available:
            raise ValueError(f"missing source session bar for {market} {session_date}")
        return _scheduled_session(market, session_date, calendars)
    raise ValueError("no source session open after decision timestamp")


__all__ = [
    "CALENDAR_PACKAGE",
    "CALENDAR_PACKAGE_VERSION",
    "MARKET_CALENDARS",
    "CalendarSet",
    "ScheduledSession",
    "derive_signal_clock",
    "first_open_after",
]
