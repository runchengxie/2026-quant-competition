from __future__ import annotations

import pandas as pd

from equity_lab.strategies import load_strategy_module


def test_sma_cross_strategy_builds_signal_frame() -> None:
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    rows = []
    for code in ["HK.00700", "HK.00941"]:
        price = 100.0
        for idx, date in enumerate(dates):
            price += 0.2 + idx * 0.01
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
    module = load_strategy_module("sma_cross")
    signal_df = module.build_signal_frame(
        market_df,
        short_window=5,
        long_window=10,
    )
    assert not signal_df.empty
    assert "signal" in signal_df.columns
    assert set(signal_df["code"]) == {"HK.00700", "HK.00941"}
