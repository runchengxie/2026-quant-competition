"""Strict daily price-grid validation, without filling or replay."""

import math
from datetime import date


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_prices(prices: dict) -> None:
    try:
        dates, closes = prices["dates"], prices["close"]
        if (
            not isinstance(dates, list)
            or len(dates) < 2
            or dates != sorted(set(dates))
            or not isinstance(closes, dict)
            or not closes
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
        ):
            raise ValueError
        if any(
            len(v) != len(dates) or any(not _number(x) or x <= 0 for x in v)
            for v in closes.values()
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("INVALID_ACCOUNTING_PRICES") from None
