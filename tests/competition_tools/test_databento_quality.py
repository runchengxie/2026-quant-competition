import copy
from pathlib import Path

import pytest

from competition_tools.datasets.databento_spec import pilot_spec
from competition_tools.datasets.databento_quality import inspect_rows


def rows():
    return [
        {
            "ts_event": "2025-01-02T00:00:00.000000000Z",
            "rtype": "35",
            "publisher_id": "1",
            "instrument_id": str(i + 1),
            "symbol": symbol,
            "open": "100.000000000",
            "high": "102",
            "low": "99",
            "close": "101",
            "volume": "1000",
        }
        for i, symbol in enumerate(pilot_spec(Path("/key"))["symbols"])
    ]


def calendar():
    return {
        "sessions": ["2025-01-02"],
        "calendar_name": "XNYS",
        "package_version": "fixture",
        "schedule_sha256": "a" * 64,
        "listing_verified": True,
    }


def test_raw_prices_and_late_summary_never_promoted():
    result = inspect_rows(rows(), pilot_spec(Path("/key")), calendar())
    assert result["accepted_research"] is False
    assert result["price_basis"] == "raw"
    assert result["timing"]["actual_historical_availability_verified"] is False
    assert result["timing"]["assumed_final_publication_local"] == "20:15"
    assert result["coverage"]["SPY"]["rows"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "ALIEN"},
        {"instrument_id": ""},
        {"close": "NaN"},
        {"open": "-1"},
        {"volume": "-1"},
        {"high": "100"},
        {"ts_event": "2024-01-01T00:00:00Z"},
        {"rtype": "32"},
    ],
)
def test_identity_and_quality_boundaries(changes):
    value = rows()
    value[0].update(changes)
    with pytest.raises(ValueError):
        inspect_rows(value, pilot_spec(Path("/key")), calendar())


def test_missing_sessions_never_filled_and_duplicates_fail():
    value = rows()
    c = calendar()
    c["sessions"].append("2025-01-03")
    result = inspect_rows(value, pilot_spec(Path("/key")), c)
    assert result["coverage"]["SPY"]["missing_sessions"] == ["2025-01-03"]
    with pytest.raises(ValueError, match="DUPLICATE"):
        inspect_rows(value + [copy.deepcopy(value[0])], pilot_spec(Path("/key")), c)


def test_calendar_dependency_and_listing_evidence_unverified():
    result = inspect_rows(rows(), pilot_spec(Path("/key")), {"sessions": None})
    assert "CALENDAR_UNVERIFIED" in result["issue_codes"]
    c = calendar()
    c["listing_verified"] = False
    assert (
        "LISTING_CALENDAR_UNVERIFIED"
        in inspect_rows(rows(), pilot_spec(Path("/key")), c)["issue_codes"]
    )
