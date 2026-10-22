from datetime import timedelta

import pytest

from competition_tools.datasets.dex_quality import validate_hourly_rows, normalize_chunk
from competition_tools.datasets.dex_spec import utc_hour

START = "2025-01-01T00:00:00Z"
END = "2025-04-01T00:00:00Z"
UNITS = {"price": "USD", "volume": "USD"}


def candle(hour=0):
    time = utc_hour(START) + timedelta(hours=hour)
    return dict(
        time_open=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        time_close=(time + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        open=10,
        high=12,
        low=9,
        close=11,
        volume=100,
    )


def test_empty_range_is_not_filled_or_complete():
    result = validate_hourly_rows([], start=START, end=END, units=UNITS)
    assert result["status"] == "partial"
    assert result["missing_intervals"] == 2160
    assert result["gaps"] == [{"start": START, "end": END, "hours": 2160}]


def test_half_open_boundary_and_canonical_close():
    end = candle(1)["time_open"]
    rows = normalize_chunk(
        [candle(), candle(1)], asset_id="wrapped-sol", start=START, end=end
    )
    assert len(rows) == 1
    assert rows[0]["interval_end"] == end
    assert "time_close" not in rows[0]
    assert (
        validate_hourly_rows(rows, start=START, end=end, units=UNITS)["status"]
        == "completed"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"open": True},
        {"close": float("nan")},
        {"volume": float("inf")},
        {"volume": -1},
        {"low": 12},
        {"close": 0},
        {"high": 9},
        {"time_open": "2025-01-01T00:30:00Z"},
        {"time_close": "2025-01-01T00:30:00Z"},
    ],
)
def test_invalid_hourly_values_rejected(change):
    with pytest.raises(ValueError):
        normalize_chunk(
            [candle() | change], asset_id="wrapped-sol", start=START, end=END
        )


def test_duplicate_and_outside_payload_rejected():
    for rows in ([candle(), candle()], [candle(-1)], [candle(2161)]):
        with pytest.raises(ValueError):
            normalize_chunk(rows, asset_id="wrapped-sol", start=START, end=END)


def test_unknown_volume_units_rejected():
    with pytest.raises(ValueError, match="USD_UNITS_UNVERIFIED"):
        validate_hourly_rows(
            [], start=START, end=END, units={"price": "USD", "volume": "native"}
        )


def test_exclusive_end_may_be_open_provider_boundary():
    boundary = candle(1) | {"time_close": "2025-01-01T01:30:00Z"}
    rows = normalize_chunk(
        [candle(), boundary],
        asset_id="wrapped-sol",
        start=START,
        end=candle(1)["time_open"],
    )
    assert len(rows) == 1
