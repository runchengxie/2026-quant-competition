from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    series = pd.Series(equity, copy=True).dropna().astype(float)
    if series.empty:
        return series
    running_max = series.cummax()
    return series / running_max - 1.0


def compute_daily_returns(portfolio_df: pd.DataFrame) -> pd.Series:
    if "daily_return" in portfolio_df.columns:
        returns = pd.to_numeric(portfolio_df["daily_return"], errors="coerce").fillna(0.0)
        return pd.Series(returns.to_numpy(), index=pd.to_datetime(portfolio_df["date"]))

    equity = pd.to_numeric(portfolio_df["equity"], errors="coerce")
    returns = equity.pct_change().fillna(0.0)
    return pd.Series(returns.to_numpy(), index=pd.to_datetime(portfolio_df["date"]))


def compute_sharpe_ratio(
    returns: pd.Series,
    *,
    annual_risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float | None:
    series = pd.Series(returns, copy=True).dropna().astype(float)
    if series.empty:
        return None

    rf_per_period = float(annual_risk_free_rate) / float(periods_per_year)
    excess = series - rf_per_period
    volatility = excess.std(ddof=1)
    if pd.isna(volatility) or volatility == 0.0:
        return None
    return float((excess.mean() / volatility) * (periods_per_year**0.5))


def _max_consecutive_true_streak(values: pd.Series) -> int:
    if values.empty:
        return 0
    return int(
        values.groupby((values != values.shift()).cumsum())
        .cumcount()
        .add(1)
        .where(values)
        .fillna(0)
        .max()
        or 0
    )


def _build_ic_metrics(
    signal_df: pd.DataFrame,
) -> tuple[float | None, float | None]:
    if signal_df.empty:
        return None, None

    signal_column = None
    for candidate in ("weight_score", "cnn_calibrated_probability", "cnn_probability", "signal"):
        if candidate in signal_df.columns:
            signal_column = candidate
            break
    if "future_return" in signal_df.columns:
        target_column = "future_return"
    elif "target_label" in signal_df.columns:
        target_column = "target_label"
    else:
        target_column = None
    if signal_column is None or target_column is None:
        return None, None

    frame = signal_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[[ "date", signal_column, target_column ]]
    frame["date"] = frame["date"].astype("datetime64[ns]")
    frame["date"] = frame["date"].dt.floor("D")
    frame = frame.dropna(subset=[signal_column, target_column])
    if frame.empty:
        return None, None

    ics: list[float] = []
    rank_ics: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        if len(group) < 3:
            continue
        signal_values = pd.to_numeric(group[signal_column], errors="coerce").astype(float)
        target_values = pd.to_numeric(group[target_column], errors="coerce").astype(float)
        valid = signal_values.notna() & target_values.notna()
        signal_valid = signal_values[valid]
        target_valid = target_values[valid]
        if len(signal_valid) < 3:
            continue
        if signal_valid.nunique() < 2 or target_valid.nunique() < 2:
            continue
        ics.append(float(signal_valid.corr(target_valid)))
        rank_ics.append(float(signal_valid.rank().corr(target_valid.rank())))

    if ics:
        return float(np.nanmean(ics)), float(np.nanmean(rank_ics))

    signal_values = pd.to_numeric(frame[signal_column], errors="coerce").astype(float)
    target_values = pd.to_numeric(frame[target_column], errors="coerce").astype(float)
    if len(signal_values) < 3:
        return None, None
    if signal_values.nunique() < 2 or target_values.nunique() < 2:
        return None, None

    return float(signal_values.corr(target_values)), float(
        signal_values.rank().corr(target_values.rank())
    )


def _slice_metric_signal(
    signal_df: pd.DataFrame,
    status_mask: str | None = None,
) -> pd.DataFrame:
    if signal_df.empty:
        return signal_df.copy()

    frame = signal_df.copy()
    if status_mask is None:
        return frame

    if "cnn_model_status" not in frame.columns:
        return frame.iloc[0:0].copy()

    return frame[frame["cnn_model_status"] == status_mask].copy()


def _hit_rate(signal_df: pd.DataFrame) -> float | None:
    if signal_df.empty:
        return None
    has_signal = signal_df.get("signal")
    has_label = signal_df.get("target_label")
    if has_signal is None or has_label is None:
        return None
    frame = pd.DataFrame({"signal": has_signal, "target_label": has_label}).dropna()
    if frame.empty:
        return None
    signal = pd.to_numeric(frame["signal"], errors="coerce").fillna(0.0)
    label = pd.to_numeric(frame["target_label"], errors="coerce").fillna(0.0)
    total = int((signal > 0.0).sum())
    if total <= 0:
        return None
    return float(((signal > 0.0) & (label > 0.5)).sum() / total)


def _segment_returns(portfolio_df: pd.DataFrame) -> dict[str, float]:
    if portfolio_df.empty:
        return {}
    if "daily_return" not in portfolio_df.columns:
        return {}

    returns = pd.to_numeric(portfolio_df["daily_return"], errors="coerce").fillna(0.0).astype(float)
    dates = pd.to_datetime(portfolio_df["date"]).dt.year
    yearly: dict[str, float] = {}
    for year, group in returns.groupby(dates):
        if group.empty:
            continue
        yearly[str(int(year))] = float(np.prod(1.0 + group.to_numpy()) - 1.0)

    return yearly


def _volatility_state_returns(
    signal_df: pd.DataFrame,
    portfolio_df: pd.DataFrame,
) -> dict[str, float]:
    if signal_df.empty or portfolio_df.empty or "volatility_regime" not in signal_df.columns:
        return {}
    regime_series = (
        signal_df.loc[:, ["date", "volatility_regime"]]
        .dropna()
        .copy()
    )
    regime_series["date"] = pd.to_datetime(regime_series["date"])
    regime_series["date"] = regime_series["date"].dt.floor("D")
    regime_by_date = (
        regime_series.groupby(regime_series["date"])["volatility_regime"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "unknown")
    )
    if regime_by_date.empty:
        return {}

    perf = pd.to_numeric(portfolio_df["daily_return"], errors="coerce").fillna(0.0).astype(float)
    perf = perf.reindex(portfolio_df.index).fillna(0.0)
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(portfolio_df["date"]).dt.floor("D"),
            "daily_return": perf,
        }
    )
    daily = daily.join(regime_by_date.rename("volatility_regime"), on="date")
    result: dict[str, float] = {}
    for regime, group in daily.groupby("volatility_regime"):
        if pd.isna(regime):
            continue
        if group["daily_return"].empty:
            continue
        result[str(regime)] = float(np.prod(1.0 + group["daily_return"].to_numpy()) - 1.0)
    return result


def _numeric_column_or_default(
    df: pd.DataFrame,
    column: str,
    default: float = 0.0,
) -> pd.Series:
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def compute_backtest_metrics(
    portfolio_df: pd.DataFrame,
    *,
    initial_capital: float,
    annual_risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    signal_df: pd.DataFrame | None = None,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, Any]:
    if portfolio_df.empty:
        return {
            "start_date": None,
            "end_date": None,
            "final_equity": float(initial_capital),
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": None,
            "sharpe_ratio": None,
            "max_drawdown": 0.0,
            "max_consecutive_loss_days": 0,
            "win_rate": 0.0,
            "signal_hit_rate": None,
            "ic": None,
            "rank_ic": None,
            "benchmark_return": None,
            "benchmark_volatility": None,
            "benchmark_excess_return": None,
            "yearly_returns": {},
            "volatility_regime_returns": {},
            "avg_turnover": 0.0,
            "max_gross_exposure": 0.0,
            "trading_days": 0,
        }

    dates = pd.to_datetime(portfolio_df["date"])
    equity = pd.to_numeric(portfolio_df["equity"], errors="coerce").astype(float)
    returns = compute_daily_returns(portfolio_df)
    drawdown = compute_drawdown_series(equity)

    final_equity = float(equity.iloc[-1])
    total_return = (final_equity / float(initial_capital)) - 1.0 if initial_capital else 0.0

    trading_days = int(len(portfolio_df))
    annualized_return = 0.0
    if trading_days > 1 and initial_capital > 0 and final_equity > 0:
        annualized_return = float(
            (final_equity / float(initial_capital)) ** (periods_per_year / trading_days)
            - 1.0
        )

    annualized_volatility = None
    if len(returns) > 1:
        volatility = returns.std(ddof=1)
        if not pd.isna(volatility):
            annualized_volatility = float(volatility * (periods_per_year**0.5))

    turnover = _numeric_column_or_default(portfolio_df, "turnover")
    exposure = _numeric_column_or_default(portfolio_df, "gross_exposure")
    drawdown = compute_drawdown_series(equity)
    returns_series = returns.fillna(0.0)
    negative_run = returns_series < 0.0
    max_consecutive_loss_days = _max_consecutive_true_streak(negative_run)

    signal_df_not_none = signal_df if signal_df is not None else pd.DataFrame()
    signal_hit_rate = _hit_rate(signal_df_not_none)
    ic, rank_ic = _build_ic_metrics(signal_df_not_none)
    oos_signal_df = _slice_metric_signal(signal_df_not_none, status_mask="cnn_predicted")
    oos_signal_hit_rate = _hit_rate(oos_signal_df)
    oos_ic, oos_rank_ic = _build_ic_metrics(oos_signal_df)

    in_sample_signal_df = _slice_metric_signal(signal_df_not_none)
    in_sample_signal_df = in_sample_signal_df[in_sample_signal_df["cnn_model_status"] != "cnn_predicted"] if "cnn_model_status" in in_sample_signal_df.columns else in_sample_signal_df.iloc[0:0]
    in_sample_signal_hit_rate = _hit_rate(in_sample_signal_df)
    in_sample_ic, in_sample_rank_ic = _build_ic_metrics(in_sample_signal_df)
    benchmark_excess_return = None
    benchmark_vol = None
    if benchmark_returns is not None and not pd.Series(benchmark_returns).empty:
        aligned_benchmark = pd.to_numeric(benchmark_returns, errors="coerce").astype(float).reindex(dates, method=None)
        aligned_benchmark = aligned_benchmark.fillna(0.0)
        benchmark_return = float(np.prod(1.0 + aligned_benchmark.to_numpy()) - 1.0) if len(aligned_benchmark) else None
        benchmark_excess_return = float(total_return - (benchmark_return if benchmark_return is not None else 0.0))
        b_vol = aligned_benchmark.std(ddof=1)
        benchmark_vol = float(b_vol * (periods_per_year**0.5)) if not pd.isna(b_vol) else None

    yearly_returns = _segment_returns(portfolio_df)
    volatility_regime_returns = _volatility_state_returns(signal_df_not_none, portfolio_df)

    return {
        "start_date": dates.iloc[0].date().isoformat(),
        "end_date": dates.iloc[-1].date().isoformat(),
        "final_equity": final_equity,
        "total_return": float(total_return),
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": compute_sharpe_ratio(
            returns,
            annual_risk_free_rate=annual_risk_free_rate,
            periods_per_year=periods_per_year,
        ),
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "max_consecutive_loss_days": max_consecutive_loss_days,
        "win_rate": float((returns_series > 0.0).mean()) if not returns_series.empty else 0.0,
        "signal_hit_rate": signal_hit_rate,
        "ic": ic,
        "rank_ic": rank_ic,
        "oos_signal_hit_rate": oos_signal_hit_rate,
        "oos_ic": oos_ic,
        "oos_rank_ic": oos_rank_ic,
        "is_signal_hit_rate": in_sample_signal_hit_rate,
        "is_ic": in_sample_ic,
        "is_rank_ic": in_sample_rank_ic,
        "benchmark_return": benchmark_return if "benchmark_return" in locals() else None,
        "benchmark_volatility": benchmark_vol,
        "benchmark_excess_return": benchmark_excess_return,
        "yearly_returns": yearly_returns,
        "volatility_regime_returns": volatility_regime_returns,
        "avg_turnover": float(turnover.mean()),
        "max_gross_exposure": float(exposure.max()),
        "trading_days": trading_days,
    }
