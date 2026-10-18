from __future__ import annotations

import pandas as pd

from equity_lab.backtest.engine import BacktestConfig, run_equal_weight_backtest
from equity_lab.signals.sma import generate_sma_signal


def test_sma_backtest_smoke() -> None:
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    rows = []
    for code, drift in [("HK.00700", 0.3), ("HK.00941", -0.1)]:
        price = 100.0
        for idx, date in enumerate(dates):
            price += drift + (idx % 5) * 0.05
            rows.append(
                {
                    "date": date,
                    "open": price - 0.5,
                    "high": price + 0.5,
                    "low": price - 1.0,
                    "close": price,
                    "volume": 1000 + idx,
                    "code": code,
                }
            )
    market_df = pd.DataFrame(rows)
    signal_df = generate_sma_signal(market_df, short_window=5, long_window=20)
    portfolio, positions = run_equal_weight_backtest(signal_df, BacktestConfig())
    assert not portfolio.empty
    assert not positions.empty
    assert "equity" in portfolio.columns
    assert portfolio["equity"].iloc[-1] > 0


def test_backtest_weights_apply_on_next_bar() -> None:
    signal_df = pd.DataFrame(
        [
            {"date": "2024-01-01", "code": "A", "close": 100.0, "signal": 0},
            {"date": "2024-01-02", "code": "A", "close": 110.0, "signal": 1},
            {"date": "2024-01-03", "code": "A", "close": 121.0, "signal": 1},
            {"date": "2024-01-04", "code": "A", "close": 133.1, "signal": 1},
        ]
    )

    portfolio, positions = run_equal_weight_backtest(
        signal_df,
        BacktestConfig(commission_bps=0.0, slippage_bps=0.0),
    )

    assert portfolio["daily_return"].round(6).tolist() == [0.0, 0.0, 0.1, 0.1]
    assert positions["target_weight"].round(6).tolist() == [0.0, 0.0, 1.0, 1.0]


def test_backtest_includes_dividend_in_asset_return() -> None:
    signal_df = pd.DataFrame(
        [
            {"date": "2024-01-01", "code": "A", "close": 100.0, "dividend": 0.0, "signal": 1},
            {"date": "2024-01-02", "code": "A", "close": 100.0, "dividend": 5.0, "signal": 1},
            {"date": "2024-01-03", "code": "A", "close": 100.0, "dividend": 0.0, "signal": 1},
        ]
    )

    portfolio, _positions = run_equal_weight_backtest(
        signal_df,
        BacktestConfig(commission_bps=0.0, slippage_bps=0.0),
    )

    assert portfolio["daily_return"].round(6).tolist() == [0.0, 0.05, 0.0]


def test_backtest_uses_precomputed_weights_when_present() -> None:
    signal_df = pd.DataFrame(
        [
            {"date": "2024-01-01", "code": "A", "close": 100.0, "signal": 1, "precomputed_weight": 0.25},
            {"date": "2024-01-01", "code": "B", "close": 100.0, "signal": 1, "precomputed_weight": 0.75},
            {"date": "2024-01-02", "code": "A", "close": 110.0, "signal": 1, "precomputed_weight": 0.25},
            {"date": "2024-01-02", "code": "B", "close": 100.0, "signal": 1, "precomputed_weight": 0.75},
        ]
    )

    portfolio, positions = run_equal_weight_backtest(
        signal_df,
        BacktestConfig(commission_bps=0.0, slippage_bps=0.0),
    )

    assert positions["target_weight"].round(6).tolist() == [0.0, 0.0, 0.25, 0.75]
    assert round(float(portfolio["daily_return"].iloc[-1]), 6) == 0.025


def test_backtest_applies_position_and_static_risk_limits() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=3, freq="D"):
        for code in ["A", "B", "C"]:
            rows.append({"date": date, "code": code, "close": 100.0, "signal": 1})

    _, positions = run_equal_weight_backtest(
        pd.DataFrame(rows),
        BacktestConfig(
            commission_bps=0.0,
            slippage_bps=0.0,
            max_positions=2,
            max_single_name_weight=0.3,
            max_gross_exposure=0.5,
        ),
    )

    active = positions[positions["date"] == pd.Timestamp("2024-01-02")]
    assert active.set_index("code")["target_weight"].round(6).to_dict() == {
        "A": 0.25,
        "B": 0.25,
        "C": 0.0,
    }
    assert round(float(active["target_weight"].sum()), 6) == 0.5


def test_backtest_applies_daily_turnover_limit() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=3, freq="D"):
        for code in ["A", "B"]:
            rows.append({"date": date, "code": code, "close": 100.0, "signal": 1})

    _, positions = run_equal_weight_backtest(
        pd.DataFrame(rows),
        BacktestConfig(
            commission_bps=0.0,
            slippage_bps=0.0,
            max_daily_turnover=0.3,
        ),
    )

    first_entry = positions[positions["date"] == pd.Timestamp("2024-01-02")]
    assert first_entry.set_index("code")["target_weight"].round(6).to_dict() == {
        "A": 0.15,
        "B": 0.15,
    }
    assert round(float(first_entry["turnover"].sum()), 6) == 0.3
