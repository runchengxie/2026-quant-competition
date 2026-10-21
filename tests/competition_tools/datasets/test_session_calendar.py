"""Real exchange schedules govern complete daily bars."""

from datetime import datetime, timezone
import importlib.util
import pytest
from competition_tools.datasets.session_calendar import completed_sessions


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("exchange_calendars") is None,
    reason="Optional daily-data profile required",
)


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "calendar,start,end,as_of,expected",
    [
        ("XNYS", "2024-07-03", "2024-07-05", "2024-07-05T19:00", ["2024-07-03"]),
        ("XNYS", "2024-11-29", "2024-11-29", "2024-11-29T18:01", ["2024-11-29"]),
        ("XNYS", "2024-03-11", "2024-03-11", "2024-03-11T19:59", []),
        ("XNYS", "2024-03-11", "2024-03-11", "2024-03-11T20:01", ["2024-03-11"]),
        ("XHKG", "2024-02-09", "2024-02-12", "2024-02-09T04:01", ["2024-02-09"]),
        ("XHKG", "2024-02-08", "2024-02-08", "2024-02-08T05:00", []),
    ],
)
def test_completed_exchange_sessions(calendar, start, end, as_of, expected):
    result = completed_sessions(calendar, start, end, as_of=stamp(as_of))
    assert result["sessions"] == expected
    assert len(result["schedule_sha256"]) == 64
    assert result["calendar_name"] == calendar
    assert result["package_version"] == "4.13.2"


def test_schedule_hash_is_replayable():
    args = ("XNYS", "2024-07-01", "2024-07-05")
    assert completed_sessions(
        *args, as_of=stamp("2024-07-06T00:00")
    ) == completed_sessions(*args, as_of=stamp("2024-07-06T00:00"))
