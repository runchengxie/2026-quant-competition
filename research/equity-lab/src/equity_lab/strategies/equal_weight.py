from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import load_universe_file

STRATEGY_NAME = "equal_weight"
DEFAULT_CONFIG_NAME = "equal_weight"
DISPLAY_NAME = "Equal Weight"
DESCRIPTION = "Baseline strategy that assigns equal pre-computed weight to all tradable names in each bar date."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS = {}
SIGNAL_NAME = "equal_weight"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(market_df: pd.DataFrame, **_kwargs: object) -> pd.DataFrame:
    df = market_df.copy().sort_values(["date", "code"]).reset_index(drop=True)
    if df.empty:
        return df

    by_date = df.groupby("date", sort=False)["code"].transform("count")
    df["precomputed_weight"] = 1.0 / by_date
    df["signal"] = 1
    df["weight_score"] = df["precomputed_weight"]
    return df
