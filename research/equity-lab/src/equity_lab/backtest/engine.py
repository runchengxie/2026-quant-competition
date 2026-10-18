# Backtest calculation:
# Convert signals to weights.
# Derive turnover and costs from weights.
# Aggregate instrument returns into portfolio performance.

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 100000.0
    commission_bps: float = 8.0
    slippage_bps: float = 12.0
    regulation_bps: float = 0.0
    sec_fee_bps: float = 0.0
    max_positions: int | None = None
    max_single_name_weight: float | None = None
    max_gross_exposure: float | None = None
    max_daily_turnover: float | None = None


def _clean_non_negative_series(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0.0).astype(float)


def _select_top_positions(
    df: pd.DataFrame,
    scores: pd.Series,
    max_positions: int | None,
) -> pd.Series:
    if max_positions is None:
        return scores

    limit = int(max_positions)
    if limit <= 0:
        return pd.Series(0.0, index=df.index, dtype=float)

    selected = pd.Series(False, index=df.index)
    ranking_frame = df[["date", "code"]].copy()
    ranking_frame["_score"] = scores

    for _, group in ranking_frame[ranking_frame["_score"] > 0].groupby("date", sort=False):
        keep_index = (
            group.sort_values(["_score", "code"], ascending=[False, True])
            .head(limit)
            .index
        )
        selected.loc[keep_index] = True

    return scores.where(selected, 0.0)


def _normalize_scores_by_date(scores: pd.Series, dates: pd.Series) -> pd.Series:
    totals = scores.groupby(dates).transform("sum")
    return scores.where(totals <= 0, scores / totals).where(totals > 0, 0.0)


def _build_raw_weights(df: pd.DataFrame, config: BacktestConfig) -> pd.Series:
    if "precomputed_weight" in df.columns:
        scores = _clean_non_negative_series(df["precomputed_weight"])
        return _select_top_positions(df, scores, config.max_positions)

    if "weight_score" in df.columns:
        scores = _clean_non_negative_series(df["weight_score"])
        scores = _select_top_positions(df, scores, config.max_positions)
        return _normalize_scores_by_date(scores, df["date"])

    scores = _clean_non_negative_series(df["signal"])
    scores = _select_top_positions(df, scores, config.max_positions)
    return _normalize_scores_by_date(scores, df["date"])


def _apply_static_weight_limits(weights: pd.Series, dates: pd.Series, config: BacktestConfig) -> pd.Series:
    limited = weights.fillna(0.0).clip(lower=0.0)

    if config.max_single_name_weight is not None:
        max_weight = max(float(config.max_single_name_weight), 0.0)
        limited = limited.clip(upper=max_weight)

    if config.max_gross_exposure is not None:
        max_gross = max(float(config.max_gross_exposure), 0.0)
        gross = limited.groupby(dates).transform("sum")
        scale = pd.Series(1.0, index=limited.index, dtype=float)
        mask = gross > max_gross
        scale.loc[mask] = np.where(gross.loc[mask] > 0.0, max_gross / gross.loc[mask], 0.0)
        limited = limited * scale

    return limited.fillna(0.0)


def _apply_daily_turnover_limit(
    df: pd.DataFrame,
    desired_target_weight: pd.Series,
    max_daily_turnover: float | None,
) -> pd.Series:
    if max_daily_turnover is None:
        return desired_target_weight.fillna(0.0)

    limit = max(float(max_daily_turnover), 0.0)
    target_weight = pd.Series(0.0, index=df.index, dtype=float)
    previous_by_code = {str(code): 0.0 for code in df["code"].astype(str).unique()}

    for _, group in df.groupby("date", sort=True):
        previous = group["code"].astype(str).map(previous_by_code).astype(float)
        desired = desired_target_weight.loc[group.index].fillna(0.0).astype(float)
        delta = desired.to_numpy(dtype=float) - previous.to_numpy(dtype=float)
        turnover = float(np.abs(delta).sum())

        if turnover > limit and turnover > 0.0:
            delta = delta * (limit / turnover)

        actual = previous.to_numpy(dtype=float) + delta
        target_weight.loc[group.index] = actual
        for code, value in zip(group["code"].astype(str), actual, strict=True):
            previous_by_code[str(code)] = float(value)

    return target_weight.fillna(0.0)


def run_equal_weight_backtest(signal_df: pd.DataFrame, config: BacktestConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = signal_df.copy().sort_values(["date", "code"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    if "dividend" not in df.columns:
        df["dividend"] = 0.0
    df["dividend"] = pd.to_numeric(df["dividend"], errors="coerce").fillna(0.0)
    prev_close = df.groupby("code")["close"].shift(1)
    df["asset_return"] = ((df["close"] + df["dividend"]) / prev_close - 1.0).replace(
        [float("inf"), float("-inf")],
        pd.NA,
    ).fillna(0.0)

    raw_weight = _build_raw_weights(df, config)
    df["raw_weight"] = _apply_static_weight_limits(raw_weight, df["date"], config)
    desired_target_weight = df.groupby("code")["raw_weight"].shift(1).fillna(0.0)
    df["target_weight"] = _apply_daily_turnover_limit(
        df,
        desired_target_weight,
        config.max_daily_turnover,
    )
    df["prev_weight"] = df.groupby("code")["target_weight"].shift(1).fillna(0.0)


    df["turnover"] = (df["target_weight"] - df["prev_weight"]).abs()
    total_cost_rate = (
        config.commission_bps
        + config.slippage_bps
        + config.regulation_bps
        + config.sec_fee_bps
    ) / 10000.0
    df["cost"] = df["turnover"] * total_cost_rate
    df["strategy_return"] = df["target_weight"] * df["asset_return"] - df["cost"]

    portfolio = (
        df.groupby("date", as_index=False)
        .agg(
            gross_exposure=("target_weight", "sum"),
            turnover=("turnover", "sum"),
            daily_return=("strategy_return", "sum"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    portfolio["equity"] = config.initial_capital * (1.0 + portfolio["daily_return"]).cumprod()
    portfolio["cum_return"] = portfolio["equity"] / config.initial_capital - 1.0
    portfolio["running_max"] = portfolio["equity"].cummax()
    portfolio["drawdown"] = portfolio["equity"] / portfolio["running_max"] - 1.0
    portfolio["drawdown_max"] = portfolio["drawdown"].min()
    return portfolio, df
