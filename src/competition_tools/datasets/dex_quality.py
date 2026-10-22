"""Hourly USD candle validation, with explicit missing intervals and no imputation."""

import math
from datetime import timedelta, datetime, timezone

from .dex_spec import utc_hour

FIELDS = {
    "asset_id",
    "time_open",
    "interval_end",
    "open",
    "high",
    "low",
    "close",
    "volume",
}
NUMERIC = ("open", "high", "low", "close", "volume")
UNITS = {"price": "USD", "volume": "USD"}


def stamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_values(row):
    if any(
        type(row[k]) not in (int, float) or not math.isfinite(row[k]) for k in NUMERIC
    ):
        raise ValueError("INVALID_CANDLE_NUMBER")
    if min(row[k] for k in NUMERIC[:-1]) <= 0 or row["volume"] < 0:
        raise ValueError("INVALID_CANDLE_NUMBER")
    if (
        not row["low"]
        <= min(row["open"], row["close"])
        <= max(row["open"], row["close"])
        <= row["high"]
    ):
        raise ValueError("INVALID_OHLC_ORDER")


def normalize_chunk(rows, *, asset_id, start, end):
    if not isinstance(rows, list):
        raise ValueError("INVALID_CANDLE_RESPONSE")
    first, stop = utc_hour(start), utc_hour(end)
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not {
            "time_open",
            "time_close",
            *NUMERIC,
        } <= set(row):
            raise ValueError("INVALID_CANDLE_RESPONSE")
        opened = utc_hour(row["time_open"])
        if opened < first or opened > stop:
            raise ValueError("OUT_OF_RANGE_CANDLE")
        if opened in seen:
            raise ValueError("DUPLICATE_CANDLE")
        seen.add(opened)
        validate_values(row)
        if opened == stop:
            continue  # Inclusive provider endpoint; retained raw for overlap comparison.
        close = utc_hour(row["time_close"])
        if close != opened + timedelta(hours=1):
            raise ValueError("INCOMPLETE_CANDLE")
        if close > datetime.now(timezone.utc):
            raise ValueError("INCOMPLETE_CANDLE")
        result.append(
            {
                "asset_id": asset_id,
                "time_open": stamp(opened),
                "interval_end": stamp(close),
                **{k: row[k] for k in NUMERIC},
            }
        )
    return sorted(result, key=lambda row: row["time_open"])


def validate_hourly_rows(rows, *, start, end, units):
    if units != UNITS:
        raise ValueError("USD_UNITS_UNVERIFIED")
    first, stop = utc_hour(start), utc_hour(end)
    if first >= stop or stop > datetime.now(timezone.utc):
        raise ValueError("INVALID_CANDLE_RANGE")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("INVALID_NORMALIZED_CANDLE")
        opened, close = utc_hour(row["time_open"]), utc_hour(row["interval_end"])
        validate_values(row)
        if (
            not first <= opened < stop
            or close != opened + timedelta(hours=1)
            or opened in seen
        ):
            raise ValueError("INVALID_NORMALIZED_CANDLE")
        seen.add(opened)
    gaps, cursor = [], first
    while cursor < stop:
        if cursor in seen:
            cursor += timedelta(hours=1)
            continue
        gap_start = cursor
        while cursor < stop and cursor not in seen:
            cursor += timedelta(hours=1)
        gaps.append(
            {
                "start": stamp(gap_start),
                "end": stamp(cursor),
                "hours": int((cursor - gap_start).total_seconds() / 3600),
            }
        )
    expected = int((stop - first).total_seconds() / 3600)
    return {
        "schema": "competition.dex_coverage.v1",
        "status": "completed" if not gaps else "partial",
        "start": start,
        "end": end,
        "expected_intervals": expected,
        "observed_intervals": len(seen),
        "missing_intervals": expected - len(seen),
        "gaps": gaps,
    }
