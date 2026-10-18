from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_lab.data.market_data import load_market_panel, load_symbol_bars, save_bars


def test_save_and_load_symbol_bars_sorts_and_deduplicates(tmp_path: Path) -> None:
    path = tmp_path / "HK_00700.csv"
    save_bars(
        pd.DataFrame(
            [
                {"date": "2024-01-02", "code": "HK.00700", "open": 2, "high": 3, "low": 1, "close": 2, "volume": 20},
                {"date": "2024-01-01", "code": "HK.00700", "open": 1, "high": 2, "low": 1, "close": 1, "volume": 10},
                {"date": "2024-01-02", "code": "HK.00700", "open": 4, "high": 5, "low": 3, "close": 4, "volume": 40},
            ]
        ),
        path,
    )

    loaded = load_symbol_bars(path)

    assert loaded["date"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01", "2024-01-02"]
    assert loaded["close"].tolist() == [1, 4]


def test_load_symbol_bars_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame([{"date": "2024-01-01", "code": "HK.00700"}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing columns"):
        load_symbol_bars(path)


def test_load_market_panel_raises_for_missing_symbol_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing market data"):
        load_market_panel(tmp_path, ["HK.00700"])


def test_load_market_panel_combines_symbol_files(tmp_path: Path) -> None:
    for code, close in [("HK.00700", 10.0), ("HK.00941", 20.0)]:
        path = tmp_path / f"{code.replace('.', '_')}.csv"
        pd.DataFrame(
            [
                {
                    "date": "2024-01-01",
                    "code": code,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 100,
                }
            ]
        ).to_csv(path, index=False)

    panel = load_market_panel(tmp_path, ["HK.00941", "HK.00700"])

    assert panel["code"].tolist() == ["HK.00700", "HK.00941"]
