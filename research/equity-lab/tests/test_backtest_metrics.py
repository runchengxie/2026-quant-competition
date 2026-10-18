from __future__ import annotations

import pandas as pd

from equity_lab.backtest.metrics import compute_backtest_metrics


def test_compute_backtest_metrics_returns_expected_summary() -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.0,
                "equity": 100000.0,
                "turnover": 0.0,
                "gross_exposure": 0.0,
            },
            {
                "date": "2024-01-02",
                "daily_return": 0.10,
                "equity": 110000.0,
                "turnover": 1.0,
                "gross_exposure": 1.0,
            },
            {
                "date": "2024-01-03",
                "daily_return": -0.05,
                "equity": 104500.0,
                "turnover": 0.2,
                "gross_exposure": 1.0,
            },
            {
                "date": "2024-01-04",
                "daily_return": 0.02,
                "equity": 106590.0,
                "turnover": 0.1,
                "gross_exposure": 1.0,
            },
        ]
    )

    metrics = compute_backtest_metrics(portfolio_df, initial_capital=100000.0)

    assert metrics["start_date"] == "2024-01-01"
    assert metrics["end_date"] == "2024-01-04"
    assert round(metrics["final_equity"], 2) == 106590.0
    assert round(metrics["total_return"], 6) == 0.0659
    assert round(metrics["max_drawdown"], 6) == -0.05
    assert round(metrics["avg_turnover"], 6) == 0.325
    assert metrics["trading_days"] == 4


def test_compute_backtest_metrics_with_new_fields() -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.01,
                "equity": 101000.0,
                "turnover": 0.2,
                "gross_exposure": 1.0,
            },
            {
                "date": "2024-01-02",
                "daily_return": 0.02,
                "equity": 103020.0,
                "turnover": 0.5,
                "gross_exposure": 1.1,
            },
            {
                "date": "2024-01-03",
                "daily_return": -0.03,
                "equity": 99929.4,
                "turnover": 0.3,
                "gross_exposure": 1.2,
            },
            {
                "date": "2024-01-04",
                "daily_return": -0.01,
                "equity": 98930.106,
                "turnover": 0.4,
                "gross_exposure": 1.1,
            },
            {
                "date": "2024-01-05",
                "daily_return": 0.015,
                "equity": 100446.95709,
                "turnover": 0.1,
                "gross_exposure": 1.0,
            },
        ]
    )
    signal_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "signal": 1,
                "target_label": 1,
                "weight_score": 0.12,
            },
            {
                "date": "2024-01-02",
                "signal": 0,
                "target_label": 0,
                "weight_score": 0.0,
            },
            {
                "date": "2024-01-03",
                "signal": 1,
                "target_label": 0,
                "weight_score": 0.08,
            },
            {
                "date": "2024-01-04",
                "signal": 0,
                "target_label": 1,
                "weight_score": 0.0,
            },
            {
                "date": "2024-01-05",
                "signal": 1,
                "target_label": 1,
                "weight_score": 0.2,
            },
        ]
    )
    benchmark_returns = pd.Series(
        [0.005, 0.01, -0.01, 0.0, 0.012],
        index=pd.to_datetime(
            [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
            ]
        ),
    )

    metrics = compute_backtest_metrics(
        portfolio_df,
        initial_capital=100000.0,
        signal_df=signal_df,
        benchmark_returns=benchmark_returns,
    )

    assert metrics["max_consecutive_loss_days"] == 2
    assert metrics["signal_hit_rate"] == 2 / 3
    assert metrics["ic"] is not None
    assert metrics["rank_ic"] is not None
    assert metrics["benchmark_return"] is not None
    assert metrics["benchmark_volatility"] is not None
    assert metrics["benchmark_excess_return"] is not None
    assert isinstance(metrics["yearly_returns"], dict)
    assert isinstance(metrics["volatility_regime_returns"], dict)
    assert "max_consecutive_loss_days" in metrics


def test_compute_backtest_metrics_empty_signal_df_is_compatible() -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.0,
                "equity": 100000.0,
                "turnover": 0.0,
                "gross_exposure": 0.0,
            },
            {
                "date": "2024-01-02",
                "daily_return": -0.02,
                "equity": 98000.0,
                "turnover": 0.2,
                "gross_exposure": 0.8,
            },
        ]
    )
    metrics = compute_backtest_metrics(portfolio_df, initial_capital=100000.0, signal_df=pd.DataFrame())

    assert metrics["signal_hit_rate"] is None
    assert metrics["ic"] is None
    assert metrics["rank_ic"] is None
    assert isinstance(metrics["max_consecutive_loss_days"], int)
    assert metrics["max_consecutive_loss_days"] >= 1
