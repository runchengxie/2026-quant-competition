# Backtest calculation:
# Portfolio policies convert signals to weights in equity_lab.portfolio.
# Derive turnover and costs from weights.
# Aggregate instrument returns into portfolio performance.

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from equity_lab.portfolio.construction import (
    apply_daily_turnover_limit,
    apply_static_weight_limits,
    build_raw_weights,
)


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


def run_equal_weight_backtest(
    signal_df: pd.DataFrame, config: BacktestConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = signal_df.copy().sort_values(["date", "code"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    if "dividend" not in df.columns:
        df["dividend"] = 0.0
    df["dividend"] = pd.to_numeric(df["dividend"], errors="coerce").fillna(0.0)
    prev_close = df.groupby("code")["close"].shift(1)
    df["asset_return"] = (
        ((df["close"] + df["dividend"]) / prev_close - 1.0)
        .replace(
            [float("inf"), float("-inf")],
            pd.NA,
        )
        .fillna(0.0)
    )

    raw_weight = build_raw_weights(df, config)
    df["raw_weight"] = apply_static_weight_limits(raw_weight, df["date"], config)
    desired_target_weight = df.groupby("code")["raw_weight"].shift(1).fillna(0.0)
    df["target_weight"] = apply_daily_turnover_limit(
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
    portfolio["equity"] = (
        config.initial_capital * (1.0 + portfolio["daily_return"]).cumprod()
    )
    portfolio["cum_return"] = portfolio["equity"] / config.initial_capital - 1.0
    portfolio["running_max"] = portfolio["equity"].cummax()
    portfolio["drawdown"] = portfolio["equity"] / portfolio["running_max"] - 1.0
    portfolio["drawdown_max"] = portfolio["drawdown"].min()
    return portfolio, df
