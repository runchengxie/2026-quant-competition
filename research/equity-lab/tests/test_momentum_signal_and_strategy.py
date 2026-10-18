from __future__ import annotations

import pandas as pd

from equity_lab.signals.momentum import generate_momentum_signal
from equity_lab.strategies import load_strategy_module


def _sample_market_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    rows = []
    for code, drift in [("HK.00700", 0.4), ("HK.00941", -0.1)]:
        price = 100.0
        for idx, date in enumerate(dates):
            price += drift + (idx % 3) * 0.05
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
    return pd.DataFrame(rows)


def test_generate_momentum_signal_smoke() -> None:
    signal_df = generate_momentum_signal(
        _sample_market_df(),
        lookback_days=5,
        min_momentum=0.0,
    )
    assert "momentum_return" in signal_df.columns
    assert "signal" in signal_df.columns


def test_momentum_strategy_builds_signal_frame() -> None:
    module = load_strategy_module("momentum_20d")
    signal_df = module.build_signal_frame(
        _sample_market_df(),
        lookback_days=5,
        min_momentum=0.0,
    )
    assert not signal_df.empty
    assert "signal" in signal_df.columns
    assert "momentum_return" in signal_df.columns
