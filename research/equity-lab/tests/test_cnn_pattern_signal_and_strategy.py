from __future__ import annotations

import pandas as pd

from equity_lab.backtest import BacktestConfig, run_equal_weight_backtest
from equity_lab.signals.cnn_pattern import generate_cnn_pattern_signal
from equity_lab.strategies import load_strategy_module


def _sample_market_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    rows = []
    for code, drift, wave in [
        ("HK.00700", 0.45, 0.25),
        ("HK.00941", -0.05, 0.35),
        ("US.AAPL", 0.25, 0.2),
    ]:
        price = 100.0
        for idx, date in enumerate(dates):
            seasonal = ((idx % 6) - 2) * wave
            price += drift + seasonal * 0.08
            rows.append(
                {
                    "date": date,
                    "open": price - 0.7 + seasonal * 0.05,
                    "high": price + 0.9 + abs(seasonal) * 0.1,
                    "low": price - 1.1 - abs(seasonal) * 0.08,
                    "close": price,
                    "volume": 1000 + idx * 7 + int(abs(seasonal) * 20),
                    "code": code,
                }
            )
    return pd.DataFrame(rows)


def test_generate_cnn_pattern_signal_smoke() -> None:
    signal_df = generate_cnn_pattern_signal(
        _sample_market_df(),
        window_size=12,
        horizon=3,
        positive_return_threshold=0.01,
        probability_threshold=0.52,
        epochs=8,
        filters=4,
        learning_rate=0.02,
    )
    assert "cnn_probability" in signal_df.columns
    assert "cnn_score" in signal_df.columns
    assert "signal" in signal_df.columns
    assert signal_df["cnn_probability"].between(0.0, 1.0).all()


def test_cnn_pattern_strategy_builds_signal_frame() -> None:
    module = load_strategy_module("cnn_pattern")
    signal_df = module.build_signal_frame(
        _sample_market_df(),
        window_size=12,
        horizon=3,
        positive_return_threshold=0.01,
        probability_threshold=0.52,
        epochs=8,
        filters=4,
        learning_rate=0.02,
    )
    assert not signal_df.empty
    assert "signal" in signal_df.columns
    assert "cnn_probability" in signal_df.columns
    assert "cnn_train_end_date" in signal_df.columns
    assert "cnn_train_count" in signal_df.columns
    assert "cnn_sample_count" in signal_df.columns


def test_cnn_pattern_signal_uses_temporal_split() -> None:
    # Split multi-symbol samples chronologically, not by concatenated symbol order.
    signal_df = generate_cnn_pattern_signal(
        _sample_market_df(),
        window_size=12,
        horizon=3,
        positive_return_threshold=0.01,
        probability_threshold=0.52,
        train_ratio=0.5,
        split_by_date=True,
        epochs=8,
        filters=4,
        learning_rate=0.02,
    )
    assert signal_df["cnn_split_by_date"].eq(True).all()
    train_end = pd.to_datetime(signal_df["cnn_train_end_date"].iloc[0])
    assert not pd.isna(train_end)
    # Require samples on both sides of the split.
    assert int(signal_df["cnn_train_count"].iloc[0]) > 0
    assert int(signal_df["cnn_test_count"].iloc[0]) > 0
    assert int(signal_df["cnn_train_count"].iloc[0]) + int(signal_df["cnn_test_count"].iloc[0]) == int(signal_df["cnn_sample_count"].iloc[0])


def test_cnn_pattern_signal_backtest_smoke() -> None:
    # Regression: synthetic samples through CNN signals and backtesting.
    signal_df = generate_cnn_pattern_signal(
        _sample_market_df(),
        window_size=12,
        horizon=3,
        positive_return_threshold=0.01,
        probability_threshold=0.52,
        train_ratio=0.55,
        split_by_date=True,
        epochs=6,
        filters=4,
        learning_rate=0.02,
    )
    required = {"date", "code", "close", "signal"}
    assert required.issubset(set(signal_df.columns))
    assert not signal_df["close"].isna().all()

    portfolio_df, _positions = run_equal_weight_backtest(signal_df, BacktestConfig())
    assert not portfolio_df.empty
    assert "equity" in portfolio_df.columns
    assert float(portfolio_df["equity"].iloc[-1]) > 0.0
