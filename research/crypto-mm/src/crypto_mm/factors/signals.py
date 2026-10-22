"""Fixed, complete-grid hourly features and forward labels."""

import math
from datetime import datetime, timedelta, timezone

SIGNALS = [
    "momentum_24h",
    "momentum_168h",
    "volume_ratio_24h_7d",
    "momentum_volume_24h",
]
HOUR = timedelta(hours=1)


def hour(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_UTC_HOUR")
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise ValueError("INVALID_UTC_HOUR") from None
    if result.minute or result.second or result.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("INVALID_UTC_HOUR")
    return result


def grid(rows):
    result, assets = {}, set()
    for row in rows:
        if set(row) != {
            "asset_id",
            "time_open",
            "interval_end",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }:
            raise ValueError("INVALID_FACTOR_CANDLE")
        end = hour(row["interval_end"])
        if end - hour(row["time_open"]) != HOUR or end in result:
            raise ValueError("INVALID_FACTOR_GRID")
        assets.add(row["asset_id"])
        if any(
            type(row[k]) not in (int, float) or not math.isfinite(row[k])
            for k in ("open", "high", "low", "close", "volume")
        ):
            raise ValueError("INVALID_FACTOR_NUMBER")
        if (
            min(row[k] for k in ("open", "high", "low", "close")) <= 0
            or row["volume"] < 0
            or not row["low"]
            <= min(row["open"], row["close"])
            <= max(row["open"], row["close"])
            <= row["high"]
        ):
            raise ValueError("INVALID_FACTOR_NUMBER")
        result[end] = row
    if len(assets) > 1:
        raise ValueError("MIXED_FACTOR_ASSETS")
    return result


def build_signals(rows: list[dict], signal_id: str) -> list[dict]:
    if signal_id not in SIGNALS:
        raise ValueError("UNKNOWN_FACTOR_SIGNAL")
    bars = grid(rows)
    width = (
        25
        if signal_id == "momentum_24h"
        else 169
        if signal_id == "momentum_168h"
        else 192
    )
    result = []
    for time, row in sorted(bars.items()):
        value, reason = None, "INCOMPLETE_FEATURE_WINDOW"
        if all(time - i * HOUR in bars for i in range(width)):
            if signal_id.startswith("momentum_") and signal_id != "momentum_volume_24h":
                value = row["close"] / bars[time - (width - 1) * HOUR]["close"] - 1
            else:
                baseline = (
                    sum(bars[time - i * HOUR]["volume"] for i in range(24, 192)) / 7
                )
                if baseline == 0:
                    reason = "ZERO_VOLUME_BASELINE"
                else:
                    ratio = (
                        sum(bars[time - i * HOUR]["volume"] for i in range(24))
                        / baseline
                    )
                    momentum = row["close"] / bars[time - 24 * HOUR]["close"] - 1
                    value = (
                        ratio
                        if signal_id == "volume_ratio_24h_7d"
                        else momentum
                        if momentum > 0 and ratio > 1
                        else 0
                    )
        if value is not None and not math.isfinite(value):
            raise ValueError("NONFINITE_FACTOR_RESULT")
        result.append(
            {
                "timestamp": row["interval_end"],
                "value": value,
                "reason": None if value is not None else reason,
            }
        )
    return result


def forward_returns(rows, horizon):
    if type(horizon) is not int or horizon not in (6, 24):
        raise ValueError("INVALID_FACTOR_HORIZON")
    bars = grid(rows)
    result = []
    for time, row in sorted(bars.items()):
        value = None
        if all(time + i * HOUR in bars for i in range(horizon + 1)):
            value = bars[time + horizon * HOUR]["close"] / row["close"] - 1
            if not math.isfinite(value):
                raise ValueError("NONFINITE_FACTOR_RESULT")
        result.append(
            {
                "timestamp": row["interval_end"],
                "value": value,
                "reason": None if value is not None else "INCOMPLETE_TARGET_WINDOW",
            }
        )
    return result
