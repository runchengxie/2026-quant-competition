from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..signals.sma import generate_sma_signal
from .common import load_universe_file

STRATEGY_NAME = "sma_cross"
DEFAULT_CONFIG_NAME = "sim_portfolio"
DISPLAY_NAME = "SMA Cross"
DESCRIPTION = "Long-only moving-average crossover strategy built on close-price SMA signals."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS = {
    "short_window": 20,
    "long_window": 60,
}
SIGNAL_NAME = "sma"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(
    market_df: pd.DataFrame,
    *,
    short_window: int = 20,
    long_window: int = 60,
) -> pd.DataFrame:
    return generate_sma_signal(
        market_df,
        short_window=short_window,
        long_window=long_window,
    )
