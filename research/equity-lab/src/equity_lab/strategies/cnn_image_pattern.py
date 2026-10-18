from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..signals.cnn_image_pattern import generate_cnn_image_pattern_signal
from .common import load_universe_file

STRATEGY_NAME = "cnn_image_pattern"
DEFAULT_CONFIG_NAME = "cnn_image_pattern"
DISPLAY_NAME = "CNN Image Pattern"
DESCRIPTION = "Research strategy that renders K-line windows as grayscale images for a lightweight 2D CNN."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS: dict[str, Any] = {
    "window_size": 20,
    "horizon": 5,
    "positive_return_threshold": 0.005,
    "probability_threshold": 0.50,
    "train_ratio": 0.7,
    "image_size": 20,
    "image_height": None,
    "image_width": None,
    "image_style": "candlestick",
    "include_volume": True,
    "include_moving_average": False,
    "moving_average_window": None,
    "collapsed_period": None,
    "filters": 2,
    "kernel_size": 3,
    "epochs": 6,
    "learning_rate": 0.03,
    "l2": 0.0001,
    "random_state": 17,
    "max_train_samples": 600,
    "prediction_batch_size": 4096,
}
SIGNAL_NAME = "cnn_image_pattern"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def build_signal_frame(
    market_df: pd.DataFrame,
    **kwargs: Any,
) -> pd.DataFrame:
    return generate_cnn_image_pattern_signal(market_df, **kwargs)
