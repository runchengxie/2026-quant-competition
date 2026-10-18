from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from equity_lab.signals.cnn_image_pattern import (
    export_candlestick_image_samples,
    generate_cnn_image_pattern_signal,
    render_candlestick_image,
    render_ohlc_image,
)
from equity_lab.strategies import load_strategy_module


def _market_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=90, freq="B")
    rows: list[dict[str, object]] = []
    codes = ["HK.00001", "HK.00002", "HK.00003", "HK.00004"]
    for code_idx, code in enumerate(codes):
        base = 40.0 + code_idx * 8.0
        phase = code_idx * 0.9
        for day_idx, date in enumerate(dates):
            cycle = np.sin(day_idx / 4.0 + phase) * 1.5
            trend = day_idx * (0.015 + code_idx * 0.002)
            close = base + trend + cycle
            open_price = close * (1.0 - 0.004 * np.cos(day_idx / 3.0 + phase))
            high = max(open_price, close) * 1.012
            low = min(open_price, close) * 0.988
            rows.append(
                {
                    "date": date,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": 100000 + code_idx * 2000 + day_idx * 50,
                    "code": code,
                }
            )
    return pd.DataFrame(rows)


def _signal_kwargs() -> dict[str, Any]:
    return {
        "window_size": 8,
        "horizon": 2,
        "positive_return_threshold": 0.0,
        "probability_threshold": 0.45,
        "train_ratio": 0.7,
        "image_size": 20,
        "filters": 2,
        "kernel_size": 3,
        "epochs": 3,
        "learning_rate": 0.02,
        "random_state": 3,
    }


def test_render_candlestick_image_smoke() -> None:
    market_df = _market_frame()
    image = render_candlestick_image(market_df.head(8), image_size=20)

    assert image.shape == (20, 20)
    assert image.dtype == np.float32
    assert image.max() > 0.0
    assert image.min() >= 0.0


def test_render_candlestick_image_preserves_missing_bar_blank_column() -> None:
    market_df = _market_frame().head(8).copy()
    market_df.loc[3, ["open", "high", "low", "close"]] = np.nan
    image = render_candlestick_image(market_df, image_size=24)

    x_positions = np.linspace(0, 23, len(market_df)).round().astype(int)
    assert image[:, x_positions[3]].max() == 0.0
    assert image.max() > 0.0


def test_render_paper_ohlc_image_with_ma_and_volume() -> None:
    market_df = _market_frame().head(20)
    image = render_ohlc_image(
        market_df,
        image_height=64,
        image_width=60,
        include_volume=True,
        include_moving_average=True,
    )

    assert image.shape == (64, 60)
    assert image.dtype == np.float32
    assert image.max() > 0.0
    assert image[-12:, :].max() > 0.0


def test_generate_cnn_image_pattern_signal_smoke() -> None:
    signal_df = generate_cnn_image_pattern_signal(_market_frame(), **_signal_kwargs())

    assert not signal_df.empty
    assert "cnn_image_probability" in signal_df.columns
    assert "cnn_probability" in signal_df.columns
    assert "cnn_image_input" in signal_df.columns
    assert signal_df["cnn_probability"].dropna().between(0.0, 1.0).all()
    assert signal_df["signal"].isin([0, 1]).all()
    assert signal_df["target_label"].notna().any()
    assert set(signal_df["cnn_image_prediction_batch_size"].dropna()) == {4096}
    assert set(signal_df["cnn_image_input"].dropna()) == {
        "candlestick_volume_grayscale"
    }


def test_generate_cnn_image_pattern_signal_supports_paper_ohlc() -> None:
    signal_df = generate_cnn_image_pattern_signal(
        _market_frame(),
        **{
            **_signal_kwargs(),
            "window_size": 20,
            "horizon": 3,
            "image_style": "paper_ohlc",
            "include_moving_average": True,
            "collapsed_period": 2,
            "prediction_batch_size": 16,
            "max_train_samples": 40,
        },
    )

    assert not signal_df.empty
    assert "cnn_image_probability" in signal_df.columns
    assert set(signal_df["cnn_image_style"].dropna()) == {"paper_ohlc"}
    assert set(signal_df["cnn_image_height"].dropna()) == {64}
    assert set(signal_df["cnn_image_width"].dropna()) == {30}
    assert set(signal_df["cnn_image_collapsed_period"].dropna()) == {2}
    assert set(signal_df["cnn_image_include_moving_average"].dropna()) == {True}
    assert set(signal_df["cnn_image_input"].dropna()) == {
        "paper_ohlc_volume_ma_collapsed_2_grayscale"
    }


def test_export_candlestick_image_samples_writes_pngs(tmp_path: Path) -> None:
    output_dir = tmp_path / "image_samples"
    metadata = export_candlestick_image_samples(
        _market_frame(),
        output_dir,
        **{
            **_signal_kwargs(),
            "export_image_sample_count": 3,
            "export_image_scale": 2,
        },
    )

    pngs = sorted(output_dir.glob("*.png"))
    assert len(pngs) == 3
    assert (output_dir / "metadata.csv").exists()
    assert metadata["file"].tolist() == [path.name for path in pngs]
    assert metadata["target_label"].isin([0, 1]).all()


def test_cnn_image_pattern_strategy_builds_signal_frame() -> None:
    module = load_strategy_module("cnn_image_pattern")
    signal_df = module.build_signal_frame(_market_frame(), **_signal_kwargs())

    assert module.STRATEGY_NAME == "cnn_image_pattern"
    assert "cnn_image_probability" in signal_df.columns
    assert signal_df["signal"].sum() > 0
