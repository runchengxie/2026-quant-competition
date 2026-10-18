from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..signals.momentum import generate_momentum_signal
from .common import load_universe_file

STRATEGY_NAME = "momentum_20d"
DEFAULT_CONFIG_NAME = "momentum_20d"
DISPLAY_NAME = "Momentum 20D"
DESCRIPTION = "Long-only daily momentum strategy inspired by the cross-day momentum idea in factor_research."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS = {
    "lookback_days": 20,
    "min_momentum": 0.0,
}
SIGNAL_NAME = "momentum"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(
    market_df: pd.DataFrame,
    *,
    lookback_days: int = 20,
    min_momentum: float = 0.0,
) -> pd.DataFrame:
    return generate_momentum_signal(
        market_df,
        lookback_days=lookback_days,
        min_momentum=min_momentum,
    )
