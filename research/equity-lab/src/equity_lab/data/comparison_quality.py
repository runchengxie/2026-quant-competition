"""Describe observed data defects without repairing or certifying source inputs."""

import numpy as np
import pandas as pd


def _require(frame, columns):
    if (
        not isinstance(frame, pd.DataFrame)
        or frame.empty
        or not set(columns) <= set(frame)
    ):
        raise ValueError("Missing or empty quality input")


def _calendar(schedule):
    _require(schedule, ["open", "close"])
    dates = pd.DatetimeIndex(schedule.index).tz_localize(None).normalize()
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Invalid quality calendar")
    return dates


def _numeric(frame, names):
    values = frame[names].apply(pd.to_numeric, errors="coerce")
    return values, int(np.isinf(values.to_numpy(dtype=float)).sum())


def _bad_ohlc(values, names):
    opening, closing, high, low = (values[n] for n in names)
    finite = np.isfinite(values[names]).all(axis=1)
    valid = (
        finite
        & (low > 0)
        & (high >= low)
        & (high >= opening)
        & (high >= closing)
        & (low <= opening)
        & (low <= closing)
    )
    return ~valid


def audit_daily(raw, schedule):
    prices = ["open_price", "close_price", "high_price", "low_price"]
    _require(raw, ["TradeDate", "Ticker", "ResearchKey", "dollar_volume", *prices])
    calendar = _calendar(schedule)
    dates = pd.to_datetime(raw.TradeDate, errors="raise").dt.normalize()
    values, nonfinite = _numeric(raw, [*prices, "dollar_volume"])
    identities = raw.ResearchKey.astype(str)
    keys = pd.DataFrame({"date": dates, "identity": identities})
    return {
        "rows": len(raw),
        "source_codes": int(raw.Ticker.nunique()),
        "candidate_identities": int(identities.nunique()),
        "observed_sessions": int(dates.nunique()),
        "first_date": dates.min().date().isoformat(),
        "last_date": dates.max().date().isoformat(),
        "duplicate_candidate_sessions": int(keys.duplicated().sum()),
        "non_session_rows": int((~dates.isin(calendar)).sum()),
        "invalid_ohlc_rows": int(_bad_ohlc(values, prices).sum()),
        "nonfinite_numeric_values": nonfinite,
        "missing_numeric_values": int(values.isna().sum().sum()),
        "negative_dollar_volume_rows": int((values.dollar_volume < 0).sum()),
        "unresolved_identity_rows": int(identities.str.startswith("unresolved:").sum()),
        "formal_common_stock_ready": False,
        "availability_verified": False,
        "corporate_action_coverage": "incomplete",
    }


def audit_minute(raw, schedule):
    prices = ["FirstTradePrice", "LastTradePrice", "HighTradePrice", "LowTradePrice"]
    names = [*prices, "AuditTotalVolume", "CloseBidPrice", "CloseAskPrice"]
    _require(
        raw,
        ["Date", "Ticker", "TimeBarStart", "AuditSession", "AuditBarStartUTC", *names],
    )
    dates = _calendar(schedule)
    lookup = schedule.copy()
    lookup.index = dates.strftime("%Y-%m-%d")
    day = pd.to_datetime(raw.Date.astype(str), errors="raise").dt.strftime("%Y-%m-%d")
    timestamp = pd.to_datetime(raw.AuditBarStartUTC, utc=True, errors="coerce")
    opening = pd.to_datetime(day.map(lookup.open), utc=True)
    closing = pd.to_datetime(day.map(lookup.close), utc=True)
    regular = raw.AuditSession.eq("regular")
    outside = (
        timestamp.isna()
        | opening.isna()
        | (timestamp < opening)
        | (timestamp >= closing)
    )
    values, nonfinite = _numeric(raw, names)
    traded = values.AuditTotalVolume > 0
    bid, ask = values.CloseBidPrice, values.CloseAskPrice
    quote = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask > 0)
    return {
        "rows": len(raw),
        "source_codes": int(raw.Ticker.nunique()),
        "duplicate_minute_keys": int(
            raw[["Date", "Ticker", "TimeBarStart"]].duplicated().sum()
        ),
        "regular_rows": int(regular.sum()),
        "regular_rows_outside_session": int((regular & outside).sum()),
        "zero_volume_rows": int(values.AuditTotalVolume.eq(0).sum()),
        "invalid_volume_rows": int(
            (
                ~np.isfinite(values.AuditTotalVolume) | (values.AuditTotalVolume < 0)
            ).sum()
        ),
        "invalid_traded_ohlc_rows": int((traded & _bad_ohlc(values, prices)).sum()),
        "nonfinite_numeric_values": nonfinite,
        "missing_quote_rows": int((~quote).sum()),
        "crossed_quote_rows": int((quote & (ask < bid)).sum()),
        "wide_quote_rows": int(
            (quote & (ask >= bid) & ((ask - bid) / ((ask + bid) / 2) > 0.05)).sum()
        ),
        "scope": "one_bounded_row_group",
        "full_conversion_certified": False,
    }
