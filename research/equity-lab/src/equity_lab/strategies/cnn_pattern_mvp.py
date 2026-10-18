from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..signals.cnn_pattern import generate_cnn_pattern_signal
from .common import load_universe_file

STRATEGY_NAME = "cnn_pattern_mvp"
DEFAULT_CONFIG_NAME = "cnn_pattern_mvp"
DISPLAY_NAME = "CNN Pattern MVP"
DESCRIPTION = "Research strategy that uses the cnn_pattern pipeline with easier-first MVP defaults."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS = {
    "window_size": 20,
    "horizon": 5,
    "positive_return_threshold": 0.005,
    "probability_threshold": 0.50,
    "train_ratio": 0.7,
    "filters": 8,
    "kernel_size": 3,
    "epochs": 40,
    "learning_rate": 0.03,
    "l2": 0.0001,
    "random_state": 7,
}
SIGNAL_NAME = "cnn_pattern"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(
    market_df: pd.DataFrame,
    **kwargs,
) -> pd.DataFrame:
    return generate_cnn_pattern_signal(market_df, **kwargs)
