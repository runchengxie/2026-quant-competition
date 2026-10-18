from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..signals.cnn_walk_forward_rank import generate_cnn_walk_forward_rank_signal
from .common import load_universe_file

STRATEGY_NAME = "cnn_walk_forward_rank"
DEFAULT_CONFIG_NAME = "cnn_walk_forward_rank"
DISPLAY_NAME = "Walk-Forward CNN Rank"
DESCRIPTION = "Out-of-sample CNN strategy using date splits, calibrated probabilities, and daily cross-sectional ranking."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS: dict[str, Any] = {
    "window_size": 20,
    "horizon": 5,
    "label_top_quantile": 0.3,
    "min_target_zscore": 0.0,
    "train_window_days": 1260,
    "validation_window_days": 252,
    "test_window_days": 252,
    "first_test_date": "2015-01-01",
    "purge_days": 5,
    "embargo_days": 5,
    "selection_top_n": 5,
    "filters": 8,
    "kernel_size": 3,
    "epochs": 40,
    "learning_rate": 0.03,
}
SIGNAL_NAME = "cnn_walk_forward_rank"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(
    market_df: pd.DataFrame,
    **kwargs: Any,
) -> pd.DataFrame:
    return generate_cnn_walk_forward_rank_signal(market_df, **kwargs)
