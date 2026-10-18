from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from equity_lab.signals.cnn_walk_forward_rank import generate_cnn_walk_forward_rank_signal
from equity_lab.strategies import load_strategy_module


def _market_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=140, freq="B")
    rows: list[dict[str, object]] = []
    codes = ["HK.00001", "HK.00002", "HK.00003", "HK.00004"]
    for code_idx, code in enumerate(codes):
        base = 50.0 + code_idx * 6.0
        for day_idx, date in enumerate(dates):
            phase = code_idx * 0.7
            trend = day_idx * (0.02 + code_idx * 0.003)
            cycle = np.sin(day_idx / 7.0 + phase) * (1.0 + code_idx * 0.1)
            close = base + trend + cycle
            open_price = close * (1.0 - 0.002 * np.cos(day_idx / 5.0 + phase))
            high = max(open_price, close) * 1.01
            low = min(open_price, close) * 0.99
            rows.append(
                {
                    "date": date,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": 100000 + code_idx * 5000 + day_idx * 10,
                    "code": code,
                }
            )
    return pd.DataFrame(rows)


def _signal_kwargs() -> dict[str, Any]:
    return {
        "window_size": 6,
        "horizon": 2,
        "label_top_quantile": 0.5,
        "train_window_days": 45,
        "validation_window_days": 10,
        "test_window_days": 20,
        "min_train_samples": 40,
        "min_validation_samples": 16,
        "selection_top_n": 2,
        "filters": 3,
        "kernel_size": 2,
        "epochs": 4,
        "learning_rate": 0.02,
        "calibrator_epochs": 10,
        "calibrator_learning_rate": 0.05,
    }


def test_generate_cnn_walk_forward_rank_signal_smoke() -> None:
    signal_df = generate_cnn_walk_forward_rank_signal(_market_frame(), **_signal_kwargs())

    assert not signal_df.empty
    assert "cnn_calibrated_probability" in signal_df.columns
    assert "cnn_prediction_rank_pct" in signal_df.columns
    assert "target_rank_pct" in signal_df.columns
    assert "weight_score" in signal_df.columns
    assert "cnn_purge_days" in signal_df.columns
    assert "cnn_embargo_days" in signal_df.columns
    assert signal_df["cnn_walk_forward_fold"].notna().any()
    assert signal_df["cnn_calibrated_probability"].dropna().between(0.0, 1.0).all()
    assert signal_df["signal"].isin([0, 1]).all()

    selected_per_date = signal_df.groupby("date")["signal"].sum()
    assert selected_per_date.max() <= 2
    fold_stats = signal_df.attrs["cnn_walk_forward_fold_stats"]
    trained = [fold for fold in fold_stats if fold["status"] == "trained"]
    assert trained
    assert trained[0]["purge_days"] == 2
    assert trained[0]["embargo_days"] == 2
    assert "test_auc" in trained[0]
    assert "test_rank_ic" in trained[0]


def test_cnn_walk_forward_rank_strategy_builds_signal_frame() -> None:
    module = load_strategy_module("cnn_walk_forward_rank")
    signal_df = module.build_signal_frame(_market_frame(), **_signal_kwargs())

    assert module.STRATEGY_NAME == "cnn_walk_forward_rank"
    assert "weight_score" in signal_df.columns
    assert signal_df["signal"].sum() > 0
