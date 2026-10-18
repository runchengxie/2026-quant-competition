from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .cnn_pattern import _sigmoid

SIGNAL_NAME = "cnn_image_pattern"
DISPLAY_NAME = "CNN Candlestick Image Pattern Signal"
DESCRIPTION = "Renders rolling K-line windows into images and trains a lightweight 2D CNN."

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume", "code"]
IMAGE_DTYPE = np.float32


@dataclass(frozen=True)
class CNNImagePatternModel:
    conv_weight: np.ndarray
    conv_bias: np.ndarray
    dense_weight: np.ndarray
    dense_bias: float
    image_height: int
    image_width: int
    kernel_size: int


@dataclass(frozen=True)
class CNNImagePatternOptions:
    window_size: int = 20
    horizon: int = 5
    positive_return_threshold: float = 0.005
    probability_threshold: float = 0.50
    train_ratio: float = 0.7
    split_by_date: bool = True
    image_size: int = 20
    image_height: int | None = None
    image_width: int | None = None
    image_style: str = "candlestick"
    include_volume: bool = True
    include_moving_average: bool = False
    moving_average_window: int | None = None
    collapsed_period: int | None = None
    filters: int = 2
    kernel_size: int = 3
    epochs: int = 6
    learning_rate: float = 0.03
    l2: float = 1e-4
    random_state: int = 17
    max_train_samples: int | None = 600
    prediction_batch_size: int = 4096
    export_image_samples_dir: str | None = None
    export_image_sample_count: int = 20
    export_image_scale: int = 8


@dataclass(frozen=True)
class CNNImageSampleIndex:
    df: pd.DataFrame
    start_indices: np.ndarray
    row_indices: np.ndarray
    labels: np.ndarray
    sample_dates: np.ndarray

    @property
    def sample_count(self) -> int:
        return int(len(self.row_indices))


def _resolve_options(
    options: CNNImagePatternOptions | None,
    overrides: dict[str, Any],
) -> CNNImagePatternOptions:
    resolved = options or CNNImagePatternOptions()
    allowed = {field.name for field in fields(CNNImagePatternOptions)}
    unknown = set(overrides) - allowed
    if unknown:
        raise TypeError(f"unknown CNN image pattern options: {sorted(unknown)}")
    return replace(resolved, **overrides) if overrides else resolved


def _validate_options(config: CNNImagePatternOptions) -> None:
    if config.window_size <= 3:
        raise ValueError("window_size must be greater than 3")
    if config.horizon <= 0:
        raise ValueError("horizon must be positive")
    if not 0.2 <= config.train_ratio < 1.0:
        raise ValueError("train_ratio must be in [0.2, 1.0)")
    if not 0.0 < config.probability_threshold < 1.0:
        raise ValueError("probability_threshold must be between 0 and 1")
    if config.image_size < 16:
        raise ValueError("image_size must be at least 16")
    if config.image_style not in {"candlestick", "paper_ohlc"}:
        raise ValueError("image_style must be candlestick or paper_ohlc")
    image_height, image_width = _image_dimensions(config)
    if config.image_style == "candlestick" and image_height != image_width:
        raise ValueError("candlestick image_style requires square image_height and image_width")
    if image_height < 16 or image_width < 15:
        raise ValueError("image_height and image_width are too small")
    if config.moving_average_window is not None and config.moving_average_window <= 0:
        raise ValueError("moving_average_window must be positive when set")
    if config.collapsed_period is not None and config.collapsed_period <= 0:
        raise ValueError("collapsed_period must be positive when set")
    if config.filters <= 0:
        raise ValueError("filters must be positive")
    if config.kernel_size <= 0 or config.kernel_size > min(image_height, image_width):
        raise ValueError("kernel_size must be in (0, min(image_height, image_width)]")
    if config.epochs <= 0:
        raise ValueError("epochs must be positive")
    if config.max_train_samples is not None and config.max_train_samples <= 0:
        raise ValueError("max_train_samples must be positive when set")
    if config.prediction_batch_size <= 0:
        raise ValueError("prediction_batch_size must be positive")
    if config.export_image_sample_count <= 0:
        raise ValueError("export_image_sample_count must be positive")
    if config.export_image_scale <= 0:
        raise ValueError("export_image_scale must be positive")


def _validate_market_df(market_df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in market_df.columns]
    if missing:
        raise ValueError(f"market_df missing required columns: {missing}")


def _price_to_y(price: float, low: float, high: float, height: int) -> int:
    if high <= low:
        return height // 2
    scaled = (high - price) / (high - low)
    return int(np.clip(round(scaled * (height - 1)), 0, height - 1))


def _paper_ohlc_height(window_size: int) -> int:
    if window_size <= 5:
        return 32
    if window_size <= 20:
        return 64
    if window_size <= 60:
        return 96
    return max(96, int(round(window_size * 1.6)))


def _image_dimensions(config: CNNImagePatternOptions) -> tuple[int, int]:
    if config.image_style == "paper_ohlc":
        height = config.image_height or _paper_ohlc_height(config.window_size)
        width = config.image_width or max(15, int(config.window_size) * 3)
        if config.collapsed_period is not None:
            collapsed_count = int(np.ceil(config.window_size / config.collapsed_period))
            width = config.image_width or max(15, collapsed_count * 3)
        return int(height), int(width)
    return int(config.image_height or config.image_size), int(config.image_width or config.image_size)


def _image_input_name(config: CNNImagePatternOptions) -> str:
    parts = [config.image_style]
    parts.append("volume" if config.include_volume else "price")
    if config.include_moving_average:
        parts.append("ma")
    if config.collapsed_period is not None:
        parts.append(f"collapsed_{config.collapsed_period}")
    parts.append("grayscale")
    return "_".join(parts)


def _coerce_window_frame(window: pd.DataFrame) -> pd.DataFrame:
    columns = ["open", "high", "low", "close", "volume"]
    extra = [column for column in ["date", "is_missing_bar"] if column in window.columns]
    frame = window.loc[:, extra + columns].copy()
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "is_missing_bar" in frame.columns:
        frame["is_missing_bar"] = frame["is_missing_bar"].fillna(False).astype(bool)
    else:
        frame["is_missing_bar"] = False
    return frame.reset_index(drop=True)


def _valid_price_mask(frame: pd.DataFrame) -> pd.Series:
    return (
        frame[["open", "high", "low", "close"]].notna().all(axis=1)
        & ~frame["is_missing_bar"].astype(bool)
    )


def _price_bounds(
    frame: pd.DataFrame,
    valid_mask: pd.Series,
    moving_average: pd.Series | None = None,
) -> tuple[float, float] | None:
    valid = frame.loc[valid_mask]
    if valid.empty:
        return None
    lows = [float(valid["low"].min())]
    highs = [float(valid["high"].max())]
    if moving_average is not None:
        ma = pd.to_numeric(moving_average.loc[valid_mask], errors="coerce").dropna()
        if not ma.empty:
            lows.append(float(ma.min()))
            highs.append(float(ma.max()))
    price_low = min(lows)
    price_high = max(highs)
    if price_high <= price_low:
        center = float(valid["close"].iloc[-1])
        price_low = center * 0.99
        price_high = center * 1.01 if center != 0.0 else 1.0
    return price_low, price_high


def _moving_average(frame: pd.DataFrame, window: int | None) -> pd.Series:
    span = int(window or len(frame))
    return (
        pd.to_numeric(frame["close"], errors="coerce")
        .rolling(span, min_periods=1)
        .mean()
    )


def _collapse_window(window: pd.DataFrame, collapsed_period: int | None) -> pd.DataFrame:
    frame = _coerce_window_frame(window)
    if collapsed_period is None or collapsed_period <= 1:
        return frame

    rows: list[dict[str, Any]] = []
    for start in range(0, len(frame), int(collapsed_period)):
        chunk = frame.iloc[start : start + int(collapsed_period)].copy()
        valid_mask = _valid_price_mask(chunk)
        valid = chunk.loc[valid_mask]
        row: dict[str, Any] = {}
        if "date" in chunk.columns:
            row["date"] = chunk["date"].iloc[-1]
        if valid.empty:
            row.update(
                {
                    "open": np.nan,
                    "high": np.nan,
                    "low": np.nan,
                    "close": np.nan,
                    "volume": np.nan,
                    "is_missing_bar": True,
                }
            )
        else:
            row.update(
                {
                    "open": float(valid["open"].iloc[0]),
                    "high": float(valid["high"].max()),
                    "low": float(valid["low"].min()),
                    "close": float(valid["close"].iloc[-1]),
                    "volume": float(pd.to_numeric(valid["volume"], errors="coerce").fillna(0.0).sum()),
                    "is_missing_bar": False,
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _draw_line(image: np.ndarray, points: list[tuple[int, int]], value: float) -> None:
    if len(points) < 2:
        for x_pos, y_pos in points:
            image[y_pos, x_pos] = max(float(image[y_pos, x_pos]), value)
        return
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:], strict=True):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        xs = np.linspace(x0, x1, steps + 1).round().astype(int)
        ys = np.linspace(y0, y1, steps + 1).round().astype(int)
        image[ys, xs] = np.maximum(image[ys, xs], value)


def render_candlestick_image(
    window: pd.DataFrame,
    *,
    image_size: int,
    include_volume: bool = True,
    include_moving_average: bool = False,
    moving_average_window: int | None = None,
) -> np.ndarray:
    frame = _coerce_window_frame(window)
    valid_mask = _valid_price_mask(frame)
    moving_average = _moving_average(frame, moving_average_window) if include_moving_average else None
    bounds = _price_bounds(frame, valid_mask, moving_average)
    image = np.zeros((image_size, image_size), dtype=IMAGE_DTYPE)
    if bounds is None:
        return image

    price_low, price_high = bounds
    price_height = image_size if not include_volume else max(8, int(image_size * 0.78))
    volume_start = min(image_size - 1, price_height + 1)

    x_positions = np.linspace(0, image_size - 1, len(frame)).round().astype(int)
    body_half_width = max(0, image_size // max(12, len(frame) * 3))
    valid_volume = frame.loc[valid_mask, "volume"].replace(0.0, np.nan)
    volume_max = float(valid_volume.max()) if not valid_volume.dropna().empty else 0.0
    volume_band = max(1, image_size - volume_start)
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    volumes = frame["volume"].fillna(0.0).to_numpy(dtype=float)

    for idx, x_pos in enumerate(x_positions):
        if not bool(valid_mask.iloc[idx]):
            continue
        open_price = float(opens[idx])
        high_price = float(highs[idx])
        low_price = float(lows[idx])
        close_price = float(closes[idx])
        y_high = _price_to_y(high_price, price_low, price_high, price_height)
        y_low = _price_to_y(low_price, price_low, price_high, price_height)
        y_open = _price_to_y(open_price, price_low, price_high, price_height)
        y_close = _price_to_y(close_price, price_low, price_high, price_height)

        top, bottom = sorted((y_high, y_low))
        image[top : bottom + 1, x_pos] = np.maximum(image[top : bottom + 1, x_pos], 0.55)

        body_top, body_bottom = sorted((y_open, y_close))
        left = max(0, x_pos - body_half_width)
        right = min(image_size, x_pos + body_half_width + 1)
        body_intensity = 1.0 if close_price >= open_price else 0.82
        image[body_top : body_bottom + 1, left:right] = np.maximum(
            image[body_top : body_bottom + 1, left:right],
            body_intensity,
        )

        if include_volume and volume_start < image_size and volume_max > 0.0:
            volume = max(0.0, float(volumes[idx]))
            bar_height = int(np.clip(round(volume / volume_max * volume_band), 0, volume_band))
            if bar_height > 0:
                image[image_size - bar_height : image_size, left:right] = np.maximum(
                    image[image_size - bar_height : image_size, left:right],
                    0.35,
                )

    if include_moving_average and moving_average is not None:
        points: list[tuple[int, int]] = []
        for idx, x_pos in enumerate(x_positions):
            ma_value = moving_average.iloc[idx]
            if pd.isna(ma_value) or not bool(valid_mask.iloc[idx]):
                continue
            y_pos = _price_to_y(float(ma_value), price_low, price_high, price_height)
            points.append((int(x_pos), int(y_pos)))
        _draw_line(image, points, 0.72)

    return image


def render_ohlc_image(
    window: pd.DataFrame,
    *,
    image_height: int,
    image_width: int,
    include_volume: bool = True,
    include_moving_average: bool = False,
    moving_average_window: int | None = None,
) -> np.ndarray:
    frame = _coerce_window_frame(window)
    valid_mask = _valid_price_mask(frame)
    moving_average = _moving_average(frame, moving_average_window) if include_moving_average else None
    bounds = _price_bounds(frame, valid_mask, moving_average)
    image = np.zeros((image_height, image_width), dtype=IMAGE_DTYPE)
    if bounds is None:
        return image

    price_low, price_high = bounds
    price_height = image_height if not include_volume else max(8, int(image_height * 0.80))
    volume_start = min(image_height - 1, price_height + 1)
    volume_band = max(1, image_height - volume_start)
    valid_volume = frame.loc[valid_mask, "volume"].replace(0.0, np.nan)
    volume_max = float(valid_volume.max()) if not valid_volume.dropna().empty else 0.0
    slot_width = image_width / max(len(frame), 1)
    ma_points: list[tuple[int, int]] = []
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    volumes = frame["volume"].fillna(0.0).to_numpy(dtype=float)
    valid_values = valid_mask.to_numpy(dtype=bool)
    ma_values = moving_average.to_numpy(dtype=float) if moving_average is not None else None

    for idx in range(len(frame)):
        slot_left = int(np.floor(idx * slot_width))
        slot_right = int(np.ceil((idx + 1) * slot_width)) - 1
        slot_left = int(np.clip(slot_left, 0, image_width - 1))
        slot_right = int(np.clip(slot_right, slot_left, image_width - 1))
        x_mid = int(np.clip(round((slot_left + slot_right) / 2), 0, image_width - 1))
        x_open = max(slot_left, x_mid - 1)
        x_close = min(slot_right, x_mid + 1)

        if not bool(valid_values[idx]):
            continue

        y_high = _price_to_y(float(highs[idx]), price_low, price_high, price_height)
        y_low = _price_to_y(float(lows[idx]), price_low, price_high, price_height)
        y_open = _price_to_y(float(opens[idx]), price_low, price_high, price_height)
        y_close = _price_to_y(float(closes[idx]), price_low, price_high, price_height)

        top, bottom = sorted((y_high, y_low))
        image[top : bottom + 1, x_mid] = np.maximum(image[top : bottom + 1, x_mid], 1.0)
        image[y_open, x_open : x_mid + 1] = np.maximum(image[y_open, x_open : x_mid + 1], 1.0)
        image[y_close, x_mid : x_close + 1] = np.maximum(image[y_close, x_mid : x_close + 1], 1.0)

        if include_volume and volume_start < image_height and volume_max > 0.0:
            volume = max(0.0, float(volumes[idx]))
            bar_height = int(np.clip(round(volume / volume_max * volume_band), 0, volume_band))
            if bar_height > 0:
                left = max(slot_left, x_mid - 1)
                right = min(slot_right + 1, x_mid + 2)
                image[image_height - bar_height : image_height, left:right] = np.maximum(
                    image[image_height - bar_height : image_height, left:right],
                    0.35,
                )

        if include_moving_average and ma_values is not None:
            ma_value = float(ma_values[idx])
            if not np.isnan(ma_value):
                ma_points.append(
                    (
                        int(x_mid),
                        _price_to_y(float(ma_value), price_low, price_high, price_height),
                    )
                )

    if include_moving_average:
        _draw_line(image, ma_points, 0.72)

    return image


def _render_market_image(window: pd.DataFrame, config: CNNImagePatternOptions) -> np.ndarray:
    image_height, image_width = _image_dimensions(config)
    frame = _collapse_window(window, config.collapsed_period)
    if config.image_style == "paper_ohlc":
        return render_ohlc_image(
            frame,
            image_height=image_height,
            image_width=image_width,
            include_volume=config.include_volume,
            include_moving_average=config.include_moving_average,
            moving_average_window=config.moving_average_window,
        )
    return render_candlestick_image(
        frame,
        image_size=image_height,
        include_volume=config.include_volume,
        include_moving_average=config.include_moving_average,
        moving_average_window=config.moving_average_window,
    )


def _prepare_image_sample_index(
    market_df: pd.DataFrame,
    *,
    window_size: int,
    horizon: int,
    positive_return_threshold: float,
) -> CNNImageSampleIndex:
    df = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["future_return"] = np.nan

    labels: list[float] = []
    start_indices: list[int] = []
    row_indices: list[int] = []
    sample_dates: list[pd.Timestamp] = []

    for _, group in df.groupby("code", sort=False):
        group = group.sort_values("date").copy()
        future_return = group["close"].shift(-horizon) / group["close"] - 1.0
        df.loc[group.index, "future_return"] = future_return.to_numpy()
        if len(group) < window_size + horizon:
            continue
        group_dates = pd.to_datetime(group["date"]).to_numpy(dtype="datetime64[ns]")

        for end_idx in range(window_size - 1, len(group) - horizon):
            row_index = int(group.index[end_idx])
            start_indices.append(int(group.index[end_idx - window_size + 1]))
            labels.append(float(future_return.iloc[end_idx] > positive_return_threshold))
            row_indices.append(row_index)
            sample_dates.append(pd.Timestamp(str(group_dates[end_idx])))

    if not row_indices:
        raise ValueError("not enough history to build CNN image windows")

    return CNNImageSampleIndex(
        df=df,
        start_indices=np.asarray(start_indices, dtype=int),
        row_indices=np.asarray(row_indices, dtype=int),
        labels=np.asarray(labels, dtype=IMAGE_DTYPE),
        sample_dates=np.asarray(sample_dates, dtype="datetime64[ns]"),
    )


def _render_image_batch(
    sample_index: CNNImageSampleIndex,
    sample_positions: np.ndarray,
    *,
    config: CNNImagePatternOptions,
) -> np.ndarray:
    image_height, image_width = _image_dimensions(config)
    images = np.empty((len(sample_positions), image_height, image_width), dtype=IMAGE_DTYPE)
    for output_idx, sample_pos in enumerate(sample_positions):
        start_idx = int(sample_index.start_indices[sample_pos])
        row_idx = int(sample_index.row_indices[sample_pos])
        window = sample_index.df.iloc[start_idx : row_idx + 1]
        images[output_idx] = _render_market_image(window, config)
    return images


def _select_train_indices(
    sample_count: int,
    sample_dates: np.ndarray,
    config: CNNImagePatternOptions,
) -> np.ndarray:
    if config.split_by_date and len(sample_dates) > 1:
        sorted_dates = np.sort(sample_dates)
        split_pos = int(np.floor(len(sorted_dates) * config.train_ratio))
        split_pos = int(np.clip(split_pos, 1, len(sorted_dates) - 1))
        split_date = sorted_dates[split_pos - 1]
        train_mask = sample_dates <= split_date
    else:
        split_pos = max(1, min(int(sample_count * config.train_ratio), sample_count - 1))
        train_mask = np.zeros(sample_count, dtype=bool)
        train_mask[:split_pos] = True

    train_indices = np.flatnonzero(train_mask)
    if (
        config.max_train_samples is not None
        and len(train_indices) > config.max_train_samples
    ):
        selected = np.linspace(
            0,
            len(train_indices) - 1,
            int(config.max_train_samples),
        ).round().astype(int)
        train_indices = train_indices[selected]
    return train_indices


def _forward_pass(
    x_train: np.ndarray,
    model: CNNImagePatternModel,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    windows = sliding_window_view(
        x_train,
        (model.kernel_size, model.kernel_size),
        axis=(1, 2),
    )
    conv_linear = np.tensordot(
        windows,
        model.conv_weight,
        axes=([3, 4], [1, 2]),
    ) + model.conv_bias
    conv_output = np.maximum(conv_linear, 0.0)
    pooled = conv_output.mean(axis=(1, 2))
    logits = pooled @ model.dense_weight + model.dense_bias
    probability = _sigmoid(logits)
    return conv_linear, pooled, probability


def _predict_image_batch(
    images: np.ndarray,
    model: CNNImagePatternModel,
) -> tuple[np.ndarray, np.ndarray]:
    windows = sliding_window_view(
        images,
        (model.kernel_size, model.kernel_size),
        axis=(1, 2),
    )
    conv_linear = np.tensordot(
        windows,
        model.conv_weight,
        axes=([3, 4], [1, 2]),
    ) + model.conv_bias
    np.maximum(conv_linear, 0.0, out=conv_linear)
    pooled = conv_linear.mean(axis=(1, 2))
    raw_score = pooled @ model.dense_weight + model.dense_bias
    probability = _sigmoid(raw_score)
    return raw_score.astype(IMAGE_DTYPE, copy=False), probability.astype(IMAGE_DTYPE, copy=False)


def _train_model_from_images(
    images: np.ndarray,
    labels: np.ndarray,
    sample_dates: np.ndarray,
    config: CNNImagePatternOptions,
) -> CNNImagePatternModel:
    train_indices = _select_train_indices(len(images), sample_dates, config)
    return _fit_model_on_images(images[train_indices], labels[train_indices], config)


def _fit_model_on_images(
    x_train: np.ndarray,
    y_train: np.ndarray,
    config: CNNImagePatternOptions,
) -> CNNImagePatternModel:
    if np.unique(y_train).size < 2:
        raise ValueError("CNN image training set contains only one class")

    rng = np.random.default_rng(config.random_state)
    model = CNNImagePatternModel(
        conv_weight=rng.normal(
            0.0,
            0.1,
            size=(config.filters, config.kernel_size, config.kernel_size),
        ).astype(IMAGE_DTYPE),
        conv_bias=np.zeros(config.filters, dtype=IMAGE_DTYPE),
        dense_weight=rng.normal(0.0, 0.1, size=config.filters).astype(IMAGE_DTYPE),
        dense_bias=0.0,
        image_height=int(x_train.shape[1]),
        image_width=int(x_train.shape[2]),
        kernel_size=config.kernel_size,
    )

    positions_h = x_train.shape[1] - config.kernel_size + 1
    positions_w = x_train.shape[2] - config.kernel_size + 1
    spatial_count = float(positions_h * positions_w)
    for _ in range(config.epochs):
        conv_linear, pooled, probability = _forward_pass(x_train, model)
        dlogits = (probability - y_train) / len(y_train)
        grad_dense_weight = pooled.T @ dlogits + config.l2 * model.dense_weight
        grad_dense_bias = float(dlogits.sum())

        dpooled = dlogits[:, None] * model.dense_weight[None, :]
        drelu = np.repeat((dpooled / spatial_count)[:, None, :], positions_h, axis=1)
        drelu = np.repeat(drelu[:, :, None, :], positions_w, axis=2)
        dconv = drelu * (conv_linear > 0.0)

        grad_conv_bias = dconv.sum(axis=(0, 1, 2))
        windows = sliding_window_view(
            x_train,
            (config.kernel_size, config.kernel_size),
            axis=(1, 2),
        )
        grad_conv_weight = np.tensordot(
            dconv,
            windows,
            axes=([0, 1, 2], [0, 1, 2]),
        )
        grad_conv_weight += config.l2 * model.conv_weight

        model = CNNImagePatternModel(
            conv_weight=(
                model.conv_weight - config.learning_rate * grad_conv_weight
            ).astype(IMAGE_DTYPE),
            conv_bias=(
                model.conv_bias - config.learning_rate * grad_conv_bias
            ).astype(IMAGE_DTYPE),
            dense_weight=(
                model.dense_weight - config.learning_rate * grad_dense_weight
            ).astype(IMAGE_DTYPE),
            dense_bias=model.dense_bias - config.learning_rate * grad_dense_bias,
            image_height=model.image_height,
            image_width=model.image_width,
            kernel_size=model.kernel_size,
        )

    return model


def _train_model_from_sample_index(
    sample_index: CNNImageSampleIndex,
    config: CNNImagePatternOptions,
) -> CNNImagePatternModel:
    train_indices = _select_train_indices(
        sample_index.sample_count,
        sample_index.sample_dates,
        config,
    )
    x_train = _render_image_batch(sample_index, train_indices, config=config)
    return _fit_model_on_images(
        x_train,
        sample_index.labels[train_indices],
        config,
    )


def _predict_sample_index(
    sample_index: CNNImageSampleIndex,
    model: CNNImagePatternModel,
    config: CNNImagePatternOptions,
) -> tuple[np.ndarray, np.ndarray]:
    raw_score = np.empty(sample_index.sample_count, dtype=IMAGE_DTYPE)
    probability = np.empty(sample_index.sample_count, dtype=IMAGE_DTYPE)
    all_positions = np.arange(sample_index.sample_count, dtype=int)
    for start in range(0, sample_index.sample_count, config.prediction_batch_size):
        batch_positions = all_positions[start : start + config.prediction_batch_size]
        batch_images = _render_image_batch(
            sample_index,
            batch_positions,
            config=config,
        )
        batch_score, batch_probability = _predict_image_batch(batch_images, model)
        raw_score[start : start + len(batch_positions)] = batch_score
        probability[start : start + len(batch_positions)] = batch_probability
    return raw_score, probability


def export_candlestick_image_samples(
    market_df: pd.DataFrame,
    output_dir: Path | str,
    *,
    options: CNNImagePatternOptions | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    config = _resolve_options(options, overrides)
    _validate_options(config)
    _validate_market_df(market_df)
    sample_index = _prepare_image_sample_index(
        market_df,
        window_size=config.window_size,
        horizon=config.horizon,
        positive_return_threshold=config.positive_return_threshold,
    )
    return _export_image_samples(sample_index, config, Path(output_dir))


def _export_image_samples(
    sample_index: CNNImageSampleIndex,
    config: CNNImagePatternOptions,
    output_dir: Path,
) -> pd.DataFrame:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    sample_count = min(config.export_image_sample_count, sample_index.sample_count)
    selected_positions = np.linspace(
        0,
        sample_index.sample_count - 1,
        sample_count,
    ).round().astype(int)
    records: list[dict[str, Any]] = []
    for export_idx, sample_pos in enumerate(selected_positions):
        row_idx = int(sample_index.row_indices[sample_pos])
        code = str(sample_index.df.at[row_idx, "code"])
        date_value = cast(Any, sample_index.df.at[row_idx, "date"])
        date_text = pd.Timestamp(date_value).strftime("%Y-%m-%d")
        label = int(sample_index.labels[sample_pos])
        image = _render_image_batch(
            sample_index,
            np.asarray([sample_pos], dtype=int),
            config=config,
        )[0]
        if config.export_image_scale > 1:
            image = np.repeat(
                np.repeat(image, config.export_image_scale, axis=0),
                config.export_image_scale,
                axis=1,
            )
        file_name = f"sample_{export_idx:03d}_{code.replace('.', '_')}_{date_text}_label_{label}.png"
        output_path = output_dir / file_name
        plt.imsave(output_path, image, cmap="gray", vmin=0.0, vmax=1.0)
        records.append(
            {
                "file": file_name,
                "code": code,
                "date": date_text,
                "row_index": row_idx,
                "target_label": label,
                "future_return": sample_index.df.at[row_idx, "future_return"],
            }
        )

    metadata = pd.DataFrame.from_records(records)
    metadata.to_csv(output_dir / "metadata.csv", index=False)
    return metadata


def train_cnn_image_pattern_model(
    market_df: pd.DataFrame,
    *,
    options: CNNImagePatternOptions | None = None,
    **overrides: Any,
) -> CNNImagePatternModel:
    config = _resolve_options(options, overrides)
    _validate_options(config)
    _validate_market_df(market_df)
    sample_index = _prepare_image_sample_index(
        market_df,
        window_size=config.window_size,
        horizon=config.horizon,
        positive_return_threshold=config.positive_return_threshold,
    )
    return _train_model_from_sample_index(sample_index, config)


def _heuristic_probability_by_code(df: pd.DataFrame) -> pd.Series:
    parts: list[pd.Series] = []
    for _, group in df.groupby("code", sort=False):
        price_impulse = group["close"].pct_change().fillna(0.0).rolling(3).mean().fillna(0.0)
        candle_bias = (
            (group["close"] - group["open"]) / group["open"].replace(0.0, np.nan)
        ).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        score = 4.0 * price_impulse + 2.0 * candle_bias
        parts.append(pd.Series(_sigmoid(score.to_numpy(dtype=float)), index=group.index))
    if not parts:
        return pd.Series(dtype=float, index=df.index)
    return pd.concat(parts).sort_index()


def _metadata(config: CNNImagePatternOptions, sample_count: int) -> dict[str, Any]:
    image_height, image_width = _image_dimensions(config)
    return {
        "cnn_image_window_size": config.window_size,
        "cnn_image_horizon": config.horizon,
        "cnn_image_size": config.image_size,
        "cnn_image_height": image_height,
        "cnn_image_width": image_width,
        "cnn_image_style": config.image_style,
        "cnn_image_include_volume": config.include_volume,
        "cnn_image_include_moving_average": config.include_moving_average,
        "cnn_image_moving_average_window": config.moving_average_window or config.window_size,
        "cnn_image_collapsed_period": config.collapsed_period or 1,
        "cnn_image_kernel_size": config.kernel_size,
        "cnn_image_filters": config.filters,
        "cnn_image_epochs": config.epochs,
        "cnn_image_max_train_samples": config.max_train_samples,
        "cnn_image_prediction_batch_size": config.prediction_batch_size,
        "cnn_image_export_sample_count": (
            config.export_image_sample_count if config.export_image_samples_dir else 0
        ),
        "cnn_image_sample_count": sample_count,
        "cnn_image_input": _image_input_name(config),
    }


def generate_cnn_image_pattern_signal(
    market_df: pd.DataFrame,
    *,
    options: CNNImagePatternOptions | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    config = _resolve_options(options, overrides)
    _validate_options(config)
    _validate_market_df(market_df)

    try:
        sample_index = _prepare_image_sample_index(
            market_df,
            window_size=config.window_size,
            horizon=config.horizon,
            positive_return_threshold=config.positive_return_threshold,
        )
        if config.export_image_samples_dir:
            _export_image_samples(sample_index, config, Path(config.export_image_samples_dir))
        model = _train_model_from_sample_index(sample_index, config)
        raw_score, probability = _predict_sample_index(sample_index, model, config)

        signal_df = sample_index.df
        signal_df["cnn_probability"] = _heuristic_probability_by_code(signal_df)
        clipped = signal_df["cnn_probability"].clip(1e-6, 1 - 1e-6)
        signal_df["cnn_score"] = np.log(clipped / (1 - clipped))
        prediction_frame = pd.DataFrame(
            {
                "row_index": sample_index.row_indices,
                "cnn_probability": probability,
                "cnn_score": raw_score,
                "target_label": sample_index.labels,
            }
        )
        signal_df.loc[prediction_frame["row_index"], "cnn_probability"] = (
            prediction_frame["cnn_probability"].to_numpy()
        )
        signal_df.loc[prediction_frame["row_index"], "cnn_score"] = (
            prediction_frame["cnn_score"].to_numpy()
        )
        signal_df["cnn_image_probability"] = signal_df["cnn_probability"]
        signal_df["cnn_image_score"] = signal_df["cnn_score"]
        signal_df["target_label"] = np.nan
        signal_df.loc[prediction_frame["row_index"], "target_label"] = (
            prediction_frame["target_label"].to_numpy()
        )
        signal_df["signal"] = (
            signal_df["cnn_probability"].fillna(0.0) >= config.probability_threshold
        ).astype(int)
        signal_df["cnn_model_status"] = "cnn_image_model_trained"
        signal_df["cnn_fallback_reason"] = ""
        for key, value in _metadata(config, sample_index.sample_count).items():
            signal_df[key] = value
        return signal_df
    except ValueError as exc:
        fallback = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
        fallback["date"] = pd.to_datetime(fallback["date"], errors="coerce")
        fallback["future_return"] = (
            fallback.groupby("code")["close"].shift(-config.horizon)
            / fallback["close"]
            - 1.0
        )
        fallback["target_label"] = (
            fallback["future_return"] > config.positive_return_threshold
        ).astype(float)
        fallback["cnn_probability"] = _heuristic_probability_by_code(fallback)
        clipped = fallback["cnn_probability"].clip(1e-6, 1 - 1e-6)
        fallback["cnn_score"] = np.log(clipped / (1 - clipped))
        fallback["cnn_image_probability"] = fallback["cnn_probability"]
        fallback["cnn_image_score"] = fallback["cnn_score"]
        fallback["signal"] = (
            fallback["cnn_probability"] >= config.probability_threshold
        ).astype(int)
        fallback["cnn_model_status"] = "cnn_image_heuristic_fallback"
        fallback["cnn_fallback_reason"] = f"{type(exc).__name__}: {exc}"
        for key, value in _metadata(config, int(len(fallback))).items():
            fallback[key] = value
        return fallback
