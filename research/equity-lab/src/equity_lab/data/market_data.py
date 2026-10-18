# src/equity_lab/data/market_data.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class MarketDataPaths:
    root: Path

    def symbol_file(self, code: str) -> Path:
        safe_code = code.replace(".", "_")
        return self.root / f"{safe_code}.csv"


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume", "code"]


def save_bars(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out = out.sort_values("date").drop_duplicates(subset=["date", "code"], keep="last")
    out.to_csv(path, index=False)


def load_symbol_bars(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_market_panel(root: Path, codes: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    paths = MarketDataPaths(root)
    for code in codes:
        path = paths.symbol_file(code)
        if not path.exists():
            raise FileNotFoundError(f"Missing market data for {code}: {path}")
        frames.append(load_symbol_bars(path))

    return pd.concat(frames, ignore_index=True).sort_values(["date", "code"]).reset_index(drop=True)
