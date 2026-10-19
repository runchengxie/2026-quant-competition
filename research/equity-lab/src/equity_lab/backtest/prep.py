# src/equity_lab/backtest/prep.py
from __future__ import annotations

import pandas as pd

REQUIRED_MARKET_COLUMNS = ["date", "open", "high", "low", "close", "volume", "code"]


def _safe_price_bounds(group: pd.DataFrame) -> pd.DataFrame:
    for column in ["open", "high", "low", "close"]:
        group[column] = pd.to_numeric(group[column], errors="coerce")

    group["high"] = group[["high", "open", "close"]].max(axis=1)
    group["low"] = group[["low", "open", "close"]].min(axis=1)
    return group


def _build_quality_flags(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy().sort_values("date")
    group["is_zero_volume"] = group["volume"].fillna(0.0) <= 0
    group["is_missing_bar"] = group["close"].isna() | group["open"].isna()

    close = pd.to_numeric(group["close"], errors="coerce").copy()
    group["close_filled"] = close.ffill()
    return group


def _validate_market_panel(market_df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in REQUIRED_MARKET_COLUMNS if col not in market_df.columns]
    if missing:
        raise ValueError(f"market panel is missing columns: {missing}")

    df = market_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if "dividend" not in df.columns:
        df["dividend"] = 0.0
    df["dividend"] = pd.to_numeric(df["dividend"], errors="coerce").fillna(0.0)
    return df.sort_values(["code", "date"]).reset_index(drop=True)


def prepare_market_panel(
    market_df: pd.DataFrame,
    *,
    trading_dates: pd.DatetimeIndex | list[str] | None = None,
) -> pd.DataFrame:
    if trading_dates is not None:
        parsed_dates = pd.to_datetime(pd.Series(trading_dates), errors="coerce")
        valid_dates = parsed_dates.dropna()
        if valid_dates.empty:
            trading_dates = None
        else:
            trading_dates = pd.DatetimeIndex(valid_dates.unique()).sort_values()
    df = _validate_market_panel(market_df)
    master_dates = trading_dates if trading_dates is not None else pd.DatetimeIndex(
        sorted(df["date"].drop_duplicates())
    )

    aligned_frames: list[pd.DataFrame] = []
    for code, group in df.groupby("code", sort=True):
        frame = group.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        frame = frame.set_index("date").reindex(master_dates)
        frame["code"] = str(code)
        missing_before_fill = frame["close"].isna() | frame["open"].isna()
        close_missing_before_fill = frame["close"].isna()

        frame["close"] = frame["close"].ffill()
        valid_close = frame["close"].notna()
        if not valid_close.any():
            continue

        frame = frame.loc[valid_close.idxmax() :]
        prev_close = frame["close"].shift(1)
        fill_close = frame["close"].ffill()

        frame = _safe_price_bounds(frame.reset_index(names="date")).set_index("date")
        frame = _build_quality_flags(frame.reset_index(names="date")).set_index("date")

        for column in ["open", "high", "low"]:
            frame[column] = frame[column].fillna(prev_close).fillna(fill_close)
        frame["close"] = fill_close
        frame["volume"] = frame["volume"].fillna(0.0)
        frame["dividend"] = frame["dividend"].fillna(0.0)
        frame["is_halt"] = frame["is_zero_volume"]
        frame["is_missing_bar"] = missing_before_fill.reindex(frame.index)
        frame["is_interpolated"] = close_missing_before_fill.reindex(frame.index)
        frame = frame.drop(columns=["close_filled"])

        aligned_frames.append(frame.reset_index(names="date"))

    if not aligned_frames:
        return df.iloc[0:0].copy()

    return (
        pd.concat(aligned_frames, ignore_index=True)
        .sort_values(["date", "code"])
        .reset_index(drop=True)
    )
