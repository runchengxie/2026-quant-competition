from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, cast

import numpy as np
import pandas as pd

SIGNAL_NAME = "cnn_pattern"
DISPLAY_NAME = "CNN Candlestick Pattern Signal"
DESCRIPTION = "Learns historical K-line windows with a lightweight 1D CNN and emits long-only probabilities."

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume", "code"]


@dataclass(frozen=True)
class CNNPatternModel:
    conv_weight: np.ndarray
    conv_bias: np.ndarray
    dense_weight: np.ndarray
    dense_bias: float
    feature_names: tuple[str, ...]
    window_size: int
    kernel_size: int


@dataclass(frozen=True)
class CNNPatternOptions:
    window_size: int = 20
    horizon: int = 5
    positive_return_threshold: float = 0.02
    probability_threshold: float = 0.55
    train_ratio: float = 0.7
    split_by_date: bool = True
    filters: int = 8
    kernel_size: int = 3
    epochs: int = 80
    learning_rate: float = 0.03
    l2: float = 1e-4
    random_state: int = 7


def _resolve_pattern_options(
    options: CNNPatternOptions | None,
    overrides: dict[str, Any],
) -> CNNPatternOptions:
    resolved = options or CNNPatternOptions()
    allowed = {field.name for field in fields(CNNPatternOptions)}
    unknown = set(overrides) - allowed
    if unknown:
        raise TypeError(f"unknown CNN pattern options: {sorted(unknown)}")
    return replace(resolved, **overrides) if overrides else resolved


def _validate_market_df(market_df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in market_df.columns]
    if missing:
        raise ValueError(f"market_df missing required columns: {missing}")


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _build_feature_frame(group: pd.DataFrame) -> pd.DataFrame:
    feature_df = group[["date", "code", "open", "high", "low", "close", "volume"]].copy()
    feature_df["date"] = pd.to_datetime(feature_df["date"], errors="coerce")
    base_price = feature_df["open"].replace(0.0, np.nan)
    base_close = feature_df["close"].replace(0.0, np.nan)
    upper_base = feature_df[["open", "close"]].max(axis=1)
    lower_base = feature_df[["open", "close"]].min(axis=1)

    feature_df["close_return"] = feature_df["close"].pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_df["body_ratio"] = ((feature_df["close"] - feature_df["open"]) / base_price).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_df["upper_shadow_ratio"] = ((feature_df["high"] - upper_base) / base_close).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_df["lower_shadow_ratio"] = ((lower_base - feature_df["low"]) / base_close).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_df["range_ratio"] = ((feature_df["high"] - feature_df["low"]) / base_close).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_df["volume_change"] = feature_df["volume"].pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return feature_df


def _normalize_window(window: np.ndarray) -> np.ndarray:
    mean = window.mean(axis=0, keepdims=True)
    std = window.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (window - mean) / std


def _prepare_cnn_dataset(
    market_df: pd.DataFrame,
    *,
    window_size: int,
    horizon: int,
    positive_return_threshold: float,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[str, ...]]:
    feature_names = (
        "close_return",
        "body_ratio",
        "upper_shadow_ratio",
        "lower_shadow_ratio",
        "range_ratio",
        "volume_change",
    )
    df = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
    df["cnn_probability"] = np.nan
    df["cnn_score"] = np.nan
    df["future_return"] = np.nan

    samples: list[np.ndarray] = []
    labels: list[float] = []
    row_indices: list[int] = []
    sample_dates: list[pd.Timestamp] = []

    for _, group in df.groupby("code", sort=False):
        feature_df = _build_feature_frame(group)
        future_return = feature_df["close"].shift(-horizon) / feature_df["close"] - 1.0
        df.loc[feature_df.index, "future_return"] = future_return.to_numpy()

        feature_matrix = feature_df.loc[:, feature_names].to_numpy(dtype=float)
        if len(feature_df) < window_size + horizon:
            continue

        for end_idx in range(window_size - 1, len(feature_df) - horizon):
            window = feature_matrix[end_idx - window_size + 1 : end_idx + 1]
            samples.append(_normalize_window(window))
            labels.append(float(future_return.iloc[end_idx] > positive_return_threshold))
            row_indices.append(int(feature_df.index[end_idx]))
            sample_dates.append(cast(pd.Timestamp, feature_df.loc[feature_df.index[end_idx], "date"]))

    if not samples:
        raise ValueError("not enough history to build CNN pattern windows")

    return (
        df,
        np.asarray(samples, dtype=float),
        np.asarray(labels, dtype=float),
        np.asarray(row_indices, dtype=int),
        np.asarray(sample_dates, dtype="datetime64[ns]"),
        feature_names,
    )


def _forward_pass(
    x_train: np.ndarray,
    model: CNNPatternModel,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    positions = x_train.shape[1] - model.kernel_size + 1
    conv_linear = np.zeros((x_train.shape[0], positions, model.conv_weight.shape[0]), dtype=float)
    for pos in range(positions):
        segment = x_train[:, pos : pos + model.kernel_size, :]
        conv_linear[:, pos, :] = np.tensordot(
            segment,
            model.conv_weight,
            axes=([1, 2], [1, 2]),
        ) + model.conv_bias
    conv_output = np.maximum(conv_linear, 0.0)
    pooled = conv_output.mean(axis=1)
    logits = pooled @ model.dense_weight + model.dense_bias
    probability = _sigmoid(logits)
    return conv_linear, pooled, probability


def train_cnn_pattern_model(
    market_df: pd.DataFrame,
    *,
    options: CNNPatternOptions | None = None,
    **overrides: Any,
) -> CNNPatternModel:
    config = _resolve_pattern_options(options, overrides)
    if config.window_size <= 3:
        raise ValueError("window_size must be greater than 3")
    if config.horizon <= 0:
        raise ValueError("horizon must be positive")
    if not 0.2 <= config.train_ratio < 1.0:
        raise ValueError("train_ratio must be in [0.2, 1.0)")
    if config.filters <= 0:
        raise ValueError("filters must be positive")
    if config.kernel_size <= 0 or config.kernel_size > config.window_size:
        raise ValueError("kernel_size must be in (0, window_size]")
    if config.epochs <= 0:
        raise ValueError("epochs must be positive")

    _validate_market_df(market_df)
    _, features, labels, _, sample_dates, _ = _prepare_cnn_dataset(
        market_df,
        window_size=config.window_size,
        horizon=config.horizon,
        positive_return_threshold=config.positive_return_threshold,
    )

    if config.split_by_date and len(sample_dates) > 1:
        sorted_dates = np.sort(sample_dates)
        split_pos = int(np.floor(len(sorted_dates) * config.train_ratio))
        split_pos = int(np.clip(split_pos, 1, len(sorted_dates) - 1))
        split_date = sorted_dates[split_pos - 1]
        train_mask = sample_dates <= split_date
    else:
        split_pos = max(1, min(int(len(features) * config.train_ratio), len(features) - 1))
        train_mask = np.zeros(len(features), dtype=bool)
        train_mask[:split_pos] = True

    x_train = features[train_mask]
    y_train = labels[train_mask]
    if np.unique(y_train).size < 2:
        raise ValueError("CNN training set contains only one class; add more diverse history")

    rng = np.random.default_rng(config.random_state)
    model = CNNPatternModel(
        conv_weight=rng.normal(0.0, 0.1, size=(config.filters, config.kernel_size, features.shape[2])),
        conv_bias=np.zeros(config.filters, dtype=float),
        dense_weight=rng.normal(0.0, 0.1, size=config.filters),
        dense_bias=0.0,
        feature_names=(
            "close_return",
            "body_ratio",
            "upper_shadow_ratio",
            "lower_shadow_ratio",
            "range_ratio",
            "volume_change",
        ),
        window_size=config.window_size,
        kernel_size=config.kernel_size,
    )

    positions = x_train.shape[1] - config.kernel_size + 1
    for _ in range(config.epochs):
        conv_linear, pooled, probability = _forward_pass(x_train, model)
        dlogits = (probability - y_train) / len(y_train)
        grad_dense_weight = pooled.T @ dlogits + config.l2 * model.dense_weight
        grad_dense_bias = float(dlogits.sum())

        dpooled = dlogits[:, None] * model.dense_weight[None, :]
        drelu = np.repeat((dpooled / positions)[:, None, :], positions, axis=1)
        dconv = drelu * (conv_linear > 0.0)

        grad_conv_bias = dconv.sum(axis=(0, 1))
        grad_conv_weight = np.zeros_like(model.conv_weight)
        for pos in range(positions):
            segment = x_train[:, pos : pos + config.kernel_size, :]
            grad_conv_weight += np.tensordot(dconv[:, pos, :], segment, axes=([0], [0]))
        grad_conv_weight += config.l2 * model.conv_weight

        model = CNNPatternModel(
            conv_weight=model.conv_weight - config.learning_rate * grad_conv_weight,
            conv_bias=model.conv_bias - config.learning_rate * grad_conv_bias,
            dense_weight=model.dense_weight - config.learning_rate * grad_dense_weight,
            dense_bias=model.dense_bias - config.learning_rate * grad_dense_bias,
            feature_names=model.feature_names,
            window_size=model.window_size,
            kernel_size=model.kernel_size,
        )

    return model


def _build_metadata_frame(
    config: CNNPatternOptions,
    *,
    split_date: pd.Timestamp | None,
    train_count: int,
    test_count: int,
    sample_count: int,
) -> dict[str, Any]:
    return {
        "cnn_window_size": config.window_size,
        "cnn_horizon": config.horizon,
        "cnn_positive_return_threshold": config.positive_return_threshold,
        "cnn_probability_threshold": config.probability_threshold,
        "cnn_train_ratio": config.train_ratio,
        "cnn_split_by_date": config.split_by_date,
        "cnn_filters": config.filters,
        "cnn_kernel_size": config.kernel_size,
        "cnn_epochs": config.epochs,
        "cnn_learning_rate": config.learning_rate,
        "cnn_l2": config.l2,
        "cnn_train_count": train_count,
        "cnn_test_count": test_count,
        "cnn_sample_count": sample_count,
        "cnn_train_end_date": split_date if split_date is not None else pd.NaT,
        "cnn_feature_set": ",".join(
            (
                "close_return",
                "body_ratio",
                "upper_shadow_ratio",
                "lower_shadow_ratio",
                "range_ratio",
                "volume_change",
            )
        ),
    }


def _heuristic_probability(df: pd.DataFrame) -> pd.Series:
    price_impulse = df["close"].pct_change().fillna(0.0).rolling(3).mean().fillna(0.0)
    candle_bias = ((df["close"] - df["open"]) / df["open"].replace(0.0, np.nan)).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    score = 4.0 * price_impulse + 2.0 * candle_bias
    return pd.Series(_sigmoid(score.to_numpy(dtype=float)), index=df.index)


def _heuristic_probability_by_code(df: pd.DataFrame) -> pd.Series:
    parts = [
        _heuristic_probability(group)
        for _, group in df.groupby("code", sort=False)
    ]
    if not parts:
        return pd.Series(dtype=float, index=df.index)
    return pd.concat(parts).sort_index()


def generate_cnn_pattern_signal(
    market_df: pd.DataFrame,
    *,
    options: CNNPatternOptions | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    config = _resolve_pattern_options(options, overrides)
    if not 0.0 < config.probability_threshold < 1.0:
        raise ValueError("probability_threshold must be between 0 and 1")

    _validate_market_df(market_df)

    try:
        signal_df, features, labels, row_indices, sample_dates, _ = _prepare_cnn_dataset(
            market_df,
            window_size=config.window_size,
            horizon=config.horizon,
            positive_return_threshold=config.positive_return_threshold,
        )
        if config.split_by_date and len(sample_dates) > 1:
            sorted_dates = np.sort(sample_dates)
            split_pos = int(np.floor(len(sorted_dates) * config.train_ratio))
            split_pos = int(np.clip(split_pos, 1, len(sorted_dates) - 1))
            split_date = pd.to_datetime(sorted_dates[split_pos - 1])
        else:
            split_pos = max(1, min(int(len(sample_dates) * config.train_ratio), len(sample_dates) - 1))
            split_date = pd.to_datetime(signal_df["date"]).sort_values().iloc[split_pos - 1]

        model = train_cnn_pattern_model(
            market_df,
            options=config,
        )
        _, pooled, probability = _forward_pass(features, model)
        raw_score = pooled @ model.dense_weight + model.dense_bias

        heuristic_probability = _heuristic_probability_by_code(signal_df)
        signal_df["cnn_probability"] = heuristic_probability
        clipped_probability = signal_df["cnn_probability"].clip(1e-6, 1 - 1e-6)
        signal_df["cnn_score"] = np.log(clipped_probability / (1 - clipped_probability))

        prediction_frame = pd.DataFrame(
            {
                "row_index": row_indices,
                "cnn_probability": probability,
                "cnn_score": raw_score,
                "target_label": labels,
            }
        )
        signal_df.loc[prediction_frame["row_index"], "cnn_probability"] = prediction_frame["cnn_probability"].to_numpy()
        signal_df.loc[prediction_frame["row_index"], "cnn_score"] = prediction_frame["cnn_score"].to_numpy()
        signal_df["target_label"] = signal_df.get("target_label", np.nan)
        signal_df.loc[prediction_frame["row_index"], "target_label"] = prediction_frame["target_label"].to_numpy()
        signal_df["signal"] = (signal_df["cnn_probability"].fillna(0.0) >= config.probability_threshold).astype(int)
        metadata = _build_metadata_frame(
            config,
            split_date=split_date,
            train_count=int((sample_dates <= split_date).sum()),
            test_count=int((sample_dates > split_date).sum()),
            sample_count=int(len(sample_dates)),
        )
        signal_df["cnn_model_status"] = "cnn_model_trained"
        signal_df["cnn_fallback_reason"] = ""
        for key, value in metadata.items():
            signal_df[key] = value
        return signal_df
    except ValueError as exc:
        fallback = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
        fallback["cnn_model_status"] = "heuristic_fallback"
        fallback["cnn_fallback_reason"] = f"{type(exc).__name__}: {exc}"
        fallback["cnn_probability"] = _heuristic_probability_by_code(fallback)
        fallback["cnn_score"] = np.log(fallback["cnn_probability"].clip(1e-6, 1 - 1e-6) / (1 - fallback["cnn_probability"].clip(1e-6, 1 - 1e-6)))
        fallback["future_return"] = fallback.groupby("code")["close"].shift(-config.horizon) / fallback["close"] - 1.0
        fallback["target_label"] = (fallback["future_return"] > config.positive_return_threshold).astype(float)
        fallback["signal"] = (fallback["cnn_probability"] >= config.probability_threshold).astype(int)
        metadata = _build_metadata_frame(
            config,
            split_date=None,
            train_count=0,
            test_count=len(fallback),
            sample_count=len(fallback),
        )
        for key, value in metadata.items():
            fallback[key] = value
        return fallback
