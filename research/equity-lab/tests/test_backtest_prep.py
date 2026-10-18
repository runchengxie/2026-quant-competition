from __future__ import annotations

import pandas as pd

from equity_lab.backtest.prep import prepare_market_panel


def test_prepare_market_panel_aligns_dates_and_fills_missing_rows() -> None:
    market_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.0,
                "volume": 100.0,
                "code": "AAA",
            },
            {
                "date": "2024-01-03",
                "open": 10.2,
                "high": 10.6,
                "low": 10.1,
                "close": 10.4,
                "volume": 120.0,
                "code": "AAA",
            },
            {
                "date": "2024-01-01",
                "open": 20.0,
                "high": 20.5,
                "low": 19.8,
                "close": 20.0,
                "volume": 200.0,
                "code": "BBB",
            },
            {
                "date": "2024-01-02",
                "open": 20.1,
                "high": 20.4,
                "low": 20.0,
                "close": 20.2,
                "volume": 210.0,
                "code": "BBB",
            },
            {
                "date": "2024-01-03",
                "open": 20.3,
                "high": 20.7,
                "low": 20.2,
                "close": 20.6,
                "volume": 220.0,
                "code": "BBB",
            },
        ]
    )

    prepared = prepare_market_panel(market_df)
    aaa = prepared[prepared["code"] == "AAA"].reset_index(drop=True)

    assert aaa["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]
    assert aaa.loc[1, "close"] == 10.0
    assert aaa.loc[1, "open"] == 10.0
    assert aaa.loc[1, "high"] == 10.0
    assert aaa.loc[1, "low"] == 10.0
    assert aaa.loc[1, "volume"] == 0.0
    assert aaa.loc[1, "dividend"] == 0.0
