from datetime import UTC, date, datetime

import pytest
from exchange_calendars import get_calendar

from platform_compare.next_open.calendar import (
    derive_signal_clock,
    first_open_after,
)


@pytest.fixture
def calendars():
    return {
        "US": get_calendar("XNYS"),
        "HK": get_calendar("XHKG"),
        "UK": get_calendar("XLON"),
        "AU": get_calendar("XASX"),
        "SG": get_calendar("XSES"),
    }


def test_signal_clock_uses_latest_market_close(calendars):
    sessions = {"HK": date(2026, 3, 6), "US": date(2026, 3, 6)}
    actual = derive_signal_clock(date(2026, 3, 9), sessions, calendars)
    expected = calendars["US"].session_close("2026-03-06").to_pydatetime()
    assert actual == expected.astimezone(UTC)


def test_first_open_after_skips_asia_open_before_us_close(calendars):
    decision_at = datetime(2026, 3, 10, 20, 1, tzinfo=UTC)
    result = first_open_after(
        "HK", decision_at, (date(2026, 3, 10), date(2026, 3, 11)), calendars
    )
    assert result.session_date == date(2026, 3, 11)
    assert result.scheduled_open_at > decision_at


def test_calendar_resolves_holiday_and_dst_session_times(calendars):
    nyse = calendars["US"]
    assert not nyse.is_session("2026-07-03")
    before_dst = nyse.session_open("2026-03-06")
    after_dst = nyse.session_open("2026-03-09")
    assert before_dst.isoformat() == "2026-03-06T14:30:00+00:00"
    assert after_dst.isoformat() == "2026-03-09T13:30:00+00:00"


def test_first_open_after_requires_source_bar_for_calendar_session(calendars):
    with pytest.raises(ValueError, match="source session"):
        first_open_after(
            "US",
            datetime(2026, 3, 6, 15, tzinfo=UTC),
            (date(2026, 3, 6),),
            calendars,
        )
