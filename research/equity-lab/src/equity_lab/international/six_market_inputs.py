"""Validated loaders for the external six-market portfolio inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"input file does not exist: {path}")
    return pd.read_csv(path)


def load_daily_asset(path: Path, market: str) -> pd.DataFrame:
    frame = _read_csv(path)
    required = {"date", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"asset input missing columns: {missing}")
    result = frame.loc[:, ["date", "close", "volume"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["close"] = pd.to_numeric(result["close"], errors="raise")
    result["volume"] = pd.to_numeric(result["volume"], errors="raise")
    if result["date"].duplicated().any():
        raise ValueError(f"asset input has duplicate dates: {path}")
    if (result["close"] <= 0).any() or (result["volume"] < 0).any():
        raise ValueError(f"asset input has invalid close or volume: {path}")
    result = result.sort_values("date").reset_index(drop=True)
    result["market"] = str(market)
    result["currency"] = result["market"].map(
        {"US": "USD", "HK": "HKD", "UK": "GBP", "AU": "AUD", "CA": "CAD", "SG": "SGD"}
    )
    if result["currency"].isna().any():
        raise ValueError(f"unsupported market: {market}")
    return result


def load_fx_series(path: Path, currency: str) -> pd.DataFrame:
    frame = _read_csv(path)
    required = {"date", "usd_per_local"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"FX input missing columns: {missing}")
    result = frame.loc[:, ["date", "usd_per_local"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["usd_per_local"] = pd.to_numeric(result["usd_per_local"], errors="raise")
    if result["date"].duplicated().any():
        raise ValueError(f"FX input has duplicate dates: {path}")
    if (result["usd_per_local"] <= 0).any():
        raise ValueError(f"FX input has non-positive rates: {path}")
    result = result.sort_values("date").reset_index(drop=True)
    result["currency"] = str(currency)
    return result


def load_distributions(path: Path, market: str, currency: str) -> pd.DataFrame:
    frame = _read_csv(path)
    required = {"date", "cash_per_share", "currency", "source"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"distribution input missing columns: {missing}")
    result = frame.loc[:, ["date", "cash_per_share", "currency", "source"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["cash_per_share"] = pd.to_numeric(result["cash_per_share"], errors="raise")
    if result["date"].duplicated().any():
        raise ValueError(f"distribution input has duplicate dates: {path}")
    if (
        result["cash_per_share"].isna().any()
        or (~np.isfinite(result["cash_per_share"])).any()
        or result["source"].isna().any()
        or (result["source"].astype(str).str.strip() == "").any()
    ):
        raise ValueError(f"distribution input requires finite cash and source: {path}")
    if (result["cash_per_share"] < 0).any():
        raise ValueError(f"distribution input has negative cash value: {path}")
    if (result["currency"] != currency).any():
        raise ValueError(f"distribution input currency mismatch: {path}")
    result = result.sort_values("date").reset_index(drop=True)
    result["market"] = str(market)
    return result


def validate_distribution_coverage(
    distributions: dict[str, pd.DataFrame], assets: dict[str, pd.DataFrame]
) -> dict[str, dict[str, object]]:
    markets = ("US", "HK", "UK", "AU", "CA", "SG")
    result: dict[str, dict[str, object]] = {}
    for market in markets:
        frame = distributions.get(market)
        if frame is None or frame.empty:
            result[market] = {"status": "unavailable", "rows": 0}
            continue
        asset = assets.get(market)
        asset_start = asset["date"].min() if asset is not None else None
        asset_end = asset["date"].max() if asset is not None else None
        result[market] = {
            "status": "complete"
            if asset_start is not None
            and frame["date"].min() <= asset_start
            and frame["date"].max() >= asset_end
            else "partial",
            "rows": len(frame),
            "start": str(frame["date"].min().date()),
            "end": str(frame["date"].max().date()),
        }
    return result


def validate_common_history(
    assets: dict[str, pd.DataFrame],
    fx: dict[str, pd.DataFrame],
    minimum_months: int = 24,
) -> dict[str, object]:
    if set(assets) != {"US", "HK", "UK", "AU", "CA", "SG"}:
        raise ValueError("asset inputs must contain exactly US, HK, UK, AU, CA, and SG")
    required_fx = {"HKD", "GBP", "AUD", "CAD", "SGD"}
    if set(fx) != required_fx:
        raise ValueError("FX inputs must contain exactly HKD, GBP, AUD, CAD, and SGD")
    month_sets = [set(frame["date"].dt.to_period("M")) for frame in assets.values()]
    month_sets.extend(set(frame["date"].dt.to_period("M")) for frame in fx.values())
    common_months = set.intersection(*month_sets)
    if len(common_months) < minimum_months:
        raise ValueError(
            f"common history has {len(common_months)} months; minimum is {minimum_months}"
        )
    all_dates = pd.concat([frame["date"] for frame in [*assets.values(), *fx.values()]])
    return {
        "common_months": len(common_months),
        "common_start_month": str(min(common_months)),
        "common_end_month": str(max(common_months)),
        "asset_count": len(assets),
        "fx_count": len(fx),
        "min_date": str(all_dates.min().date()),
        "max_date": str(all_dates.max().date()),
    }


__all__ = [
    "load_daily_asset",
    "load_distributions",
    "load_fx_series",
    "validate_common_history",
    "validate_distribution_coverage",
]
