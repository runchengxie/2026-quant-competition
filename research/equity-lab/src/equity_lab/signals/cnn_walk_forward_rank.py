from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

import numpy as np
import pandas as pd

from .cnn_pattern import (
    CNNPatternModel,
    _build_feature_frame,
    _forward_pass,
    _normalize_window,
    _sigmoid,
)

SIGNAL_NAME = "cnn_walk_forward_rank"
DISPLAY_NAME = "Walk-Forward CNN Cross-Sectional Rank Signal"
DESCRIPTION = (
    "Trains the lightweight CNN with strict date-based walk-forward splits, "
    "calibrates validation probabilities, and selects top-ranked names out of sample."
)

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume", "code"]
FEATURE_NAMES = (
    "close_return",
    "body_ratio",
    "upper_shadow_ratio",
    "lower_shadow_ratio",
    "range_ratio",
    "volume_change",
)


@dataclass(frozen=True)
class CNNWalkForwardRankOptions:
    window_size: int = 20
    horizon: int = 5
    label_top_quantile: float = 0.3
    min_target_zscore: float = 0.0
    train_window_days: int = 1260
    validation_window_days: int = 252
    test_window_days: int = 252
    first_test_date: str | None = None
    purge_days: int | None = None
    embargo_days: int | None = None
    min_train_samples: int = 400
    min_validation_samples: int = 80
    selection_top_n: int = 5
    min_calibrated_probability: float = 0.0
    filters: int = 8
    kernel_size: int = 3
    epochs: int = 40
    learning_rate: float = 0.03
    l2: float = 1e-4
    random_state: int = 7
    calibrator_epochs: int = 200
    calibrator_learning_rate: float = 0.05
    calibrator_l2: float = 1e-3


@dataclass(frozen=True)
class ProbabilityCalibrator:
    slope: float
    intercept: float
    center: float
    scale: float

    def predict(self, raw_score: np.ndarray) -> np.ndarray:
        scale = self.scale if self.scale > 1e-12 else 1.0
        standardized = (raw_score - self.center) / scale
        return _sigmoid(self.slope * standardized + self.intercept)


def _resolve_options(
    options: CNNWalkForwardRankOptions | None,
    overrides: dict[str, Any],
) -> CNNWalkForwardRankOptions:
    resolved = options or CNNWalkForwardRankOptions()
    allowed = {field.name for field in fields(CNNWalkForwardRankOptions)}
    unknown = set(overrides) - allowed
    if unknown:
        raise TypeError(f"unknown CNN walk-forward rank options: {sorted(unknown)}")
    return replace(resolved, **overrides) if overrides else resolved


def _validate_options(config: CNNWalkForwardRankOptions) -> None:
    if config.window_size <= 3:
        raise ValueError("window_size must be greater than 3")
    if config.horizon <= 0:
        raise ValueError("horizon must be positive")
    if not 0.0 < config.label_top_quantile < 1.0:
        raise ValueError("label_top_quantile must be between 0 and 1")
    if config.train_window_days <= config.validation_window_days:
        raise ValueError("train_window_days must be greater than validation_window_days")
    if config.validation_window_days <= 0 or config.test_window_days <= 0:
        raise ValueError("validation_window_days and test_window_days must be positive")
    if config.purge_days is not None and config.purge_days < 0:
        raise ValueError("purge_days cannot be negative")
    if config.embargo_days is not None and config.embargo_days < 0:
        raise ValueError("embargo_days cannot be negative")
    if config.selection_top_n <= 0:
        raise ValueError("selection_top_n must be positive")
    if config.filters <= 0:
        raise ValueError("filters must be positive")
    if config.kernel_size <= 0 or config.kernel_size > config.window_size:
        raise ValueError("kernel_size must be in (0, window_size]")
    if config.epochs <= 0:
        raise ValueError("epochs must be positive")


def _validate_market_df(market_df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in market_df.columns]
    if missing:
        raise ValueError(f"market_df missing required columns: {missing}")


def _zscore_by_date(values: pd.Series, dates: pd.Series) -> pd.Series:
    means = values.groupby(dates).transform("mean")
    stds = values.groupby(dates).transform("std").replace(0.0, np.nan)
    return ((values - means) / stds).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _rank_pct_by_date(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates).rank(pct=True, method="average").fillna(0.0)


def _prepare_rank_dataset(
    market_df: pd.DataFrame,
    *,
    window_size: int,
    horizon: int,
    label_top_quantile: float,
    min_target_zscore: float,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    df = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df["future_return"] = np.nan

    samples: list[np.ndarray] = []
    labels: list[float] = []
    row_indices: list[int] = []

    feature_frames: dict[str, pd.DataFrame] = {}
    for code, group in df.groupby("code", sort=False):
        feature_df = _build_feature_frame(group)
        future_return = feature_df["close"].shift(-horizon) / feature_df["close"] - 1.0
        df.loc[feature_df.index, "future_return"] = future_return.to_numpy()
        feature_frames[str(code)] = feature_df

    future = pd.to_numeric(df["future_return"], errors="coerce")
    df["target_return_zscore"] = _zscore_by_date(future, df["date"])
    df["target_rank_pct"] = _rank_pct_by_date(future, df["date"])
    rank_cutoff = 1.0 - float(label_top_quantile)
    df["target_label"] = (
        (df["target_rank_pct"] >= rank_cutoff)
        & (df["target_return_zscore"] >= float(min_target_zscore))
        & future.notna()
    ).astype(float)
    future_values = future.to_numpy(dtype=float)
    label_values = df["target_label"].to_numpy(dtype=float)

    for _code, feature_df in feature_frames.items():
        feature_matrix = feature_df.loc[:, FEATURE_NAMES].to_numpy(dtype=float)
        if len(feature_df) < window_size + horizon:
            continue

        for end_idx in range(window_size - 1, len(feature_df) - horizon):
            row_index = int(feature_df.index[end_idx])
            if np.isnan(future_values[row_index]):
                continue
            window = feature_matrix[end_idx - window_size + 1 : end_idx + 1]
            samples.append(_normalize_window(window))
            labels.append(float(label_values[row_index]))
            row_indices.append(row_index)

    if not samples:
        raise ValueError("not enough history to build CNN walk-forward rank windows")

    return (
        df,
        np.asarray(samples, dtype=float),
        np.asarray(labels, dtype=float),
        np.asarray(row_indices, dtype=int),
        future.to_numpy(dtype=float),
    )


def _train_model_from_arrays(
    x_train: np.ndarray,
    y_train: np.ndarray,
    config: CNNWalkForwardRankOptions,
    *,
    fold_index: int,
) -> CNNPatternModel:
    if np.unique(y_train).size < 2:
        raise ValueError("training labels contain only one class")

    rng = np.random.default_rng(config.random_state + fold_index)
    model = CNNPatternModel(
        conv_weight=rng.normal(0.0, 0.1, size=(config.filters, config.kernel_size, x_train.shape[2])),
        conv_bias=np.zeros(config.filters, dtype=float),
        dense_weight=rng.normal(0.0, 0.1, size=config.filters),
        dense_bias=0.0,
        feature_names=FEATURE_NAMES,
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


def _raw_score(features: np.ndarray, model: CNNPatternModel) -> np.ndarray:
    _, pooled, _ = _forward_pass(features, model)
    return pooled @ model.dense_weight + model.dense_bias


def _fit_probability_calibrator(
    raw_score: np.ndarray,
    labels: np.ndarray,
    config: CNNWalkForwardRankOptions,
) -> ProbabilityCalibrator:
    raw = np.asarray(raw_score, dtype=float)
    y = np.asarray(labels, dtype=float)
    center = float(raw.mean()) if len(raw) else 0.0
    scale = float(raw.std()) if len(raw) else 1.0
    scale = scale if scale > 1e-12 else 1.0
    x = (raw - center) / scale

    base_rate = float(np.clip(y.mean() if len(y) else 0.5, 1e-3, 1.0 - 1e-3))
    slope = 0.0
    intercept = float(np.log(base_rate / (1.0 - base_rate)))
    if len(y) == 0 or np.unique(y).size < 2:
        return ProbabilityCalibrator(slope=slope, intercept=intercept, center=center, scale=scale)

    for _ in range(config.calibrator_epochs):
        probability = _sigmoid(slope * x + intercept)
        error = probability - y
        grad_slope = float((error * x).mean() + config.calibrator_l2 * slope)
        grad_intercept = float(error.mean())
        slope -= config.calibrator_learning_rate * grad_slope
        intercept -= config.calibrator_learning_rate * grad_intercept

    return ProbabilityCalibrator(slope=slope, intercept=intercept, center=center, scale=scale)


def _sample_meta(df: pd.DataFrame, labels: np.ndarray, row_indices: np.ndarray) -> pd.DataFrame:
    meta = df.loc[row_indices, ["date", "code", "future_return", "target_return_zscore", "target_rank_pct"]].copy()
    meta["sample_pos"] = np.arange(len(row_indices), dtype=int)
    meta["row_index"] = row_indices
    meta["target_label"] = labels
    return meta.reset_index(drop=True)


def _effective_purge_days(config: CNNWalkForwardRankOptions) -> int:
    return int(config.horizon if config.purge_days is None else config.purge_days)


def _effective_embargo_days(config: CNNWalkForwardRankOptions) -> int:
    return int(config.horizon if config.embargo_days is None else config.embargo_days)


def _fold_ranges(dates: pd.DatetimeIndex, config: CNNWalkForwardRankOptions):
    fold_start = config.train_window_days
    if config.first_test_date:
        first_test_date = pd.Timestamp(config.first_test_date)
        fold_start = max(fold_start, int(dates.searchsorted(first_test_date)))

    purge_days = _effective_purge_days(config)
    embargo_days = _effective_embargo_days(config)
    fold_index = 0
    while fold_start < len(dates):
        train_start = max(0, fold_start - config.train_window_days)
        validation_start = max(train_start + 1, fold_start - config.validation_window_days)
        test_end = min(fold_start + config.test_window_days, len(dates))
        train_end = max(train_start, validation_start - purge_days)
        validation_effective_start = min(fold_start, validation_start + embargo_days)
        validation_end = max(validation_effective_start, fold_start - purge_days)
        test_effective_start = min(test_end, fold_start + embargo_days)
        if (
            train_end > train_start
            and validation_end > validation_effective_start
            and test_end > test_effective_start
        ):
            yield (
                fold_index,
                dates[train_start],
                dates[train_end - 1],
                dates[validation_effective_start],
                dates[validation_end - 1],
                dates[test_effective_start],
                dates[test_end - 1],
                purge_days,
                embargo_days,
            )
        fold_index += 1
        fold_start = test_end


def _assign_rank_signals(df: pd.DataFrame, config: CNNWalkForwardRankOptions) -> pd.DataFrame:
    out = df.copy()
    out["cnn_prediction_rank_pct"] = np.nan
    out["weight_score"] = 0.0
    out["signal"] = 0

    candidates = out[out["cnn_calibrated_probability"].notna()].copy()
    if candidates.empty:
        return out

    for _, group in candidates.groupby("date", sort=True):
        ranked = group.copy()
        ranked["cnn_prediction_rank_pct"] = ranked["cnn_calibrated_probability"].rank(
            pct=True,
            method="average",
        )
        out.loc[ranked.index, "cnn_prediction_rank_pct"] = ranked["cnn_prediction_rank_pct"]

        eligible = ranked[
            ranked["cnn_calibrated_probability"] >= float(config.min_calibrated_probability)
        ]
        keep = eligible.sort_values(
            ["cnn_calibrated_probability", "code"],
            ascending=[False, True],
        ).head(config.selection_top_n)
        out.loc[keep.index, "weight_score"] = keep["cnn_calibrated_probability"].clip(lower=0.0)
        out.loc[keep.index, "signal"] = 1

    return out


def _segment_signal_returns(
    meta: pd.DataFrame,
    positions: np.ndarray,
    probabilities: np.ndarray,
    labels: np.ndarray,
    future_returns: np.ndarray,
    *,
    selection_top_n: int,
    min_calibrated_probability: float,
) -> dict[str, float | int | None]:
    if len(positions) == 0:
        return {
            "mean_future_return": None,
            "selected_signal_count": 0,
            "selected_mean_future_return": None,
            "selected_hit_rate": None,
        }

    segment = pd.DataFrame(
        {
            "date": meta.loc[positions, "date"].to_numpy(),
            "probability": probabilities,
            "future_return": future_returns[positions],
            "target_label": labels[positions],
        }
    )
    segment = segment.dropna(subset=["future_return"]).copy()
    if segment.empty:
        return {
            "mean_future_return": None,
            "selected_signal_count": 0,
            "selected_mean_future_return": None,
            "selected_hit_rate": None,
        }

    segment["probability"] = pd.to_numeric(segment["probability"], errors="coerce")
    candidate = segment[segment["probability"].notna()].copy()
    if candidate.empty:
        mean_return = float(np.nanmean(segment["future_return"].to_numpy(dtype=float)))
        return {
            "mean_future_return": mean_return,
            "selected_signal_count": 0,
            "selected_mean_future_return": None,
            "selected_hit_rate": None,
        }

    candidate["rank"] = candidate.groupby("date")["probability"].rank(method="first", ascending=False)
    selected = candidate[
        (candidate["probability"] >= float(min_calibrated_probability))
        & (candidate["rank"] <= int(selection_top_n))
    ]

    mean_return = float(np.nanmean(candidate["future_return"].to_numpy(dtype=float)))
    selected_count = int(len(selected))
    if selected.empty:
        return {
            "mean_future_return": mean_return,
            "selected_signal_count": selected_count,
            "selected_mean_future_return": None,
            "selected_hit_rate": None,
        }

    selected_returns = pd.to_numeric(selected["future_return"], errors="coerce")
    selected_labels = pd.to_numeric(selected["target_label"], errors="coerce").fillna(0.0)
    return {
        "mean_future_return": mean_return,
        "selected_signal_count": selected_count,
        "selected_mean_future_return": float(selected_returns.mean())
        if not selected_returns.empty
        else None,
        "selected_hit_rate": float((selected_labels > 0.5).mean())
        if selected_count > 0
        else None,
    }


def _binary_auc(probabilities: np.ndarray, labels: np.ndarray) -> float | None:
    y = np.asarray(labels, dtype=float)
    scores = np.asarray(probabilities, dtype=float)
    valid = np.isfinite(scores) & np.isfinite(y)
    if valid.sum() < 3:
        return None
    y = y[valid] > 0.5
    scores = scores[valid]
    positive_count = int(y.sum())
    negative_count = int((~y).sum())
    if positive_count == 0 or negative_count == 0:
        return None
    ranks = pd.Series(scores).rank(method="average").to_numpy(dtype=float)
    positive_rank_sum = float(ranks[y].sum())
    auc = (
        positive_rank_sum - positive_count * (positive_count + 1) / 2.0
    ) / float(positive_count * negative_count)
    return float(auc)


def _segment_prediction_metrics(
    meta: pd.DataFrame,
    positions: np.ndarray,
    probabilities: np.ndarray,
    labels: np.ndarray,
    future_returns: np.ndarray,
) -> dict[str, float | None]:
    if len(positions) == 0:
        return {"ic": None, "rank_ic": None, "auc": None}

    segment = pd.DataFrame(
        {
            "date": meta.loc[positions, "date"].to_numpy(),
            "probability": probabilities,
            "future_return": future_returns[positions],
            "target_label": labels[positions],
        }
    ).dropna(subset=["probability", "future_return", "target_label"])
    if len(segment) < 3:
        return {"ic": None, "rank_ic": None, "auc": None}

    ics: list[float] = []
    rank_ics: list[float] = []
    for _, group in segment.groupby("date", sort=True):
        if len(group) < 3:
            continue
        probability = pd.to_numeric(group["probability"], errors="coerce")
        future_return = pd.to_numeric(group["future_return"], errors="coerce")
        valid = probability.notna() & future_return.notna()
        probability = probability[valid]
        future_return = future_return[valid]
        if len(probability) < 3:
            continue
        if probability.nunique() < 2 or future_return.nunique() < 2:
            continue
        ics.append(float(probability.corr(future_return)))
        rank_ics.append(float(probability.rank().corr(future_return.rank())))

    return {
        "ic": float(np.nanmean(ics)) if ics else None,
        "rank_ic": float(np.nanmean(rank_ics)) if rank_ics else None,
        "auc": _binary_auc(
            pd.to_numeric(segment["probability"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(segment["target_label"], errors="coerce").to_numpy(dtype=float),
        ),
    }


def _build_fold_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    return records


def generate_cnn_walk_forward_rank_signal(
    market_df: pd.DataFrame,
    *,
    options: CNNWalkForwardRankOptions | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    config = _resolve_options(options, overrides)
    _validate_options(config)
    _validate_market_df(market_df)

    base_df, features, labels, row_indices, future_values = _prepare_rank_dataset(
        market_df,
        window_size=config.window_size,
        horizon=config.horizon,
        label_top_quantile=config.label_top_quantile,
        min_target_zscore=config.min_target_zscore,
    )
    meta = _sample_meta(base_df, labels, row_indices)
    sample_dates = pd.DatetimeIndex(sorted(meta["date"].drop_duplicates()))

    result = base_df.copy()
    result["cnn_raw_score"] = np.nan
    result["cnn_probability"] = np.nan
    result["cnn_calibrated_probability"] = np.nan
    result["cnn_walk_forward_fold"] = pd.NA
    result["cnn_training_window_days"] = config.train_window_days
    result["cnn_validation_window_days"] = config.validation_window_days
    result["cnn_test_window_days"] = config.test_window_days
    result["cnn_purge_days"] = _effective_purge_days(config)
    result["cnn_embargo_days"] = _effective_embargo_days(config)
    result["cnn_label_top_quantile"] = config.label_top_quantile
    result["cnn_selection_top_n"] = config.selection_top_n
    result["cnn_model_status"] = "no_prediction"
    result["cnn_fallback_reason"] = "outside_walk_forward_window"
    result["cnn_fold_train_start"] = pd.NaT
    result["cnn_fold_train_end"] = pd.NaT
    result["cnn_fold_validation_start"] = pd.NaT
    result["cnn_fold_validation_end"] = pd.NaT
    result["cnn_fold_test_start"] = pd.NaT
    result["cnn_fold_test_end"] = pd.NaT
    fold_stats: list[dict[str, Any]] = []

    for (
        fold_index,
        train_start,
        train_end,
        validation_start,
        validation_end,
        test_start,
        test_end,
        purge_days,
        embargo_days,
    ) in _fold_ranges(sample_dates, config):
        fold_record: dict[str, Any] = {
            "fold_index": fold_index,
            "train_start": str(train_start.date()),
            "train_end": str(train_end.date()),
            "validation_start": str(validation_start.date()),
            "validation_end": str(validation_end.date()),
            "test_start": str(test_start.date()),
            "test_end": str(test_end.date()),
            "purge_days": int(purge_days),
            "embargo_days": int(embargo_days),
            "train_count": 0,
            "validation_count": 0,
            "test_count": 0,
            "status": "skipped",
            "train_mean_future_return": None,
            "train_selected_signal_count": 0,
            "train_selected_mean_future_return": None,
            "train_selected_hit_rate": None,
            "train_auc": None,
            "train_ic": None,
            "train_rank_ic": None,
            "validation_mean_future_return": None,
            "validation_selected_signal_count": 0,
            "validation_selected_mean_future_return": None,
            "validation_selected_hit_rate": None,
            "validation_auc": None,
            "validation_ic": None,
            "validation_rank_ic": None,
            "test_mean_future_return": None,
            "test_selected_signal_count": 0,
            "test_selected_mean_future_return": None,
            "test_selected_hit_rate": None,
            "test_auc": None,
            "test_ic": None,
            "test_rank_ic": None,
        }
        train_mask = (meta["date"] >= train_start) & (meta["date"] <= train_end)
        validation_mask = (meta["date"] >= validation_start) & (meta["date"] <= validation_end)
        test_mask = (meta["date"] >= test_start) & (meta["date"] <= test_end)

        train_positions = meta.loc[train_mask, "sample_pos"].to_numpy(dtype=int)
        validation_positions = meta.loc[validation_mask, "sample_pos"].to_numpy(dtype=int)
        test_positions = meta.loc[test_mask, "sample_pos"].to_numpy(dtype=int)
        fold_record["train_count"] = int(len(train_positions))
        fold_record["validation_count"] = int(len(validation_positions))
        fold_record["test_count"] = int(len(test_positions))
        if (
            len(train_positions) < config.min_train_samples
            or len(validation_positions) < config.min_validation_samples
            or len(test_positions) == 0
        ):
            fold_record["status"] = "insufficient_samples"
            fold_stats.append(fold_record)
            continue

        try:
            model = _train_model_from_arrays(
                features[train_positions],
                labels[train_positions],
                config,
                fold_index=fold_index,
            )
            fold_record["status"] = "trained"
        except ValueError:
            fold_record["status"] = "training_failed_single_class"
            fold_stats.append(fold_record)
            continue

        validation_raw = _raw_score(features[validation_positions], model)
        train_raw = _raw_score(features[train_positions], model)
        calibrator = _fit_probability_calibrator(
            validation_raw,
            labels[validation_positions],
            config,
        )
        train_calibrated = calibrator.predict(train_raw)
        validation_calibrated = calibrator.predict(validation_raw)
        train_metrics = _segment_signal_returns(
            meta=meta,
            positions=train_positions,
            probabilities=train_calibrated,
            labels=labels,
            future_returns=future_values,
            selection_top_n=config.selection_top_n,
            min_calibrated_probability=config.min_calibrated_probability,
        )
        validation_metrics = _segment_signal_returns(
            meta=meta,
            positions=validation_positions,
            probabilities=validation_calibrated,
            labels=labels,
            future_returns=future_values,
            selection_top_n=config.selection_top_n,
            min_calibrated_probability=config.min_calibrated_probability,
        )
        fold_record["train_mean_future_return"] = train_metrics["mean_future_return"]
        fold_record["train_selected_signal_count"] = train_metrics["selected_signal_count"]
        fold_record["train_selected_mean_future_return"] = train_metrics["selected_mean_future_return"]
        fold_record["train_selected_hit_rate"] = train_metrics["selected_hit_rate"]
        fold_record["validation_mean_future_return"] = validation_metrics["mean_future_return"]
        fold_record["validation_selected_signal_count"] = validation_metrics["selected_signal_count"]
        fold_record["validation_selected_mean_future_return"] = validation_metrics[
            "selected_mean_future_return"
        ]
        fold_record["validation_selected_hit_rate"] = validation_metrics["selected_hit_rate"]
        train_prediction_metrics = _segment_prediction_metrics(
            meta=meta,
            positions=train_positions,
            probabilities=train_calibrated,
            labels=labels,
            future_returns=future_values,
        )
        validation_prediction_metrics = _segment_prediction_metrics(
            meta=meta,
            positions=validation_positions,
            probabilities=validation_calibrated,
            labels=labels,
            future_returns=future_values,
        )
        fold_record["train_auc"] = train_prediction_metrics["auc"]
        fold_record["train_ic"] = train_prediction_metrics["ic"]
        fold_record["train_rank_ic"] = train_prediction_metrics["rank_ic"]
        fold_record["validation_auc"] = validation_prediction_metrics["auc"]
        fold_record["validation_ic"] = validation_prediction_metrics["ic"]
        fold_record["validation_rank_ic"] = validation_prediction_metrics["rank_ic"]

        test_raw = _raw_score(features[test_positions], model)
        test_probability = _sigmoid(test_raw)
        test_calibrated = calibrator.predict(test_raw)
        test_rows = meta.loc[test_mask, "row_index"].to_numpy(dtype=int)

        result.loc[test_rows, "cnn_raw_score"] = test_raw
        result.loc[test_rows, "cnn_probability"] = test_probability
        result.loc[test_rows, "cnn_calibrated_probability"] = test_calibrated
        result.loc[test_rows, "cnn_walk_forward_fold"] = fold_index
        result.loc[test_rows, "cnn_model_status"] = "cnn_predicted"
        result.loc[test_rows, "cnn_fallback_reason"] = ""
        result.loc[test_rows, "cnn_fold_train_start"] = pd.to_datetime(train_start)
        result.loc[test_rows, "cnn_fold_train_end"] = pd.to_datetime(train_end)
        result.loc[test_rows, "cnn_fold_validation_start"] = pd.to_datetime(validation_start)
        result.loc[test_rows, "cnn_fold_validation_end"] = pd.to_datetime(validation_end)
        result.loc[test_rows, "cnn_fold_test_start"] = pd.to_datetime(test_start)
        result.loc[test_rows, "cnn_fold_test_end"] = pd.to_datetime(test_end)

        threshold = float(config.min_calibrated_probability)
        test_hit = np.asarray(test_probability >= threshold, dtype=int)
        test_labels = labels[test_positions]
        hit_mask = (test_hit == 1) & (test_labels == 1.0)
        fold_record["test_mean_future_return"] = float(np.nanmean(future_values[test_positions]))
        fold_record["test_hit_rate"] = float(hit_mask.mean()) if len(hit_mask) else 0.0
        selected_test_labels = test_labels[test_hit == 1]
        fold_record["test_hit_rate_at_threshold"] = (
            float(selected_test_labels.sum() / len(selected_test_labels))
            if len(selected_test_labels)
            else None
        )
        fold_record["calibrator_slope"] = float(calibrator.slope)
        fold_record["calibrator_intercept"] = float(calibrator.intercept)
        test_metrics = _segment_signal_returns(
            meta=meta,
            positions=test_positions,
            probabilities=test_calibrated,
            labels=labels,
            future_returns=future_values,
            selection_top_n=config.selection_top_n,
            min_calibrated_probability=config.min_calibrated_probability,
        )
        fold_record["test_mean_future_return"] = test_metrics["mean_future_return"]
        fold_record["test_selected_signal_count"] = test_metrics["selected_signal_count"]
        fold_record["test_selected_mean_future_return"] = test_metrics[
            "selected_mean_future_return"
        ]
        fold_record["test_selected_hit_rate"] = test_metrics["selected_hit_rate"]
        test_prediction_metrics = _segment_prediction_metrics(
            meta=meta,
            positions=test_positions,
            probabilities=test_calibrated,
            labels=labels,
            future_returns=future_values,
        )
        fold_record["test_auc"] = test_prediction_metrics["auc"]
        fold_record["test_ic"] = test_prediction_metrics["ic"]
        fold_record["test_rank_ic"] = test_prediction_metrics["rank_ic"]
        fold_stats.append(fold_record)

    result.attrs["cnn_walk_forward_fold_stats"] = _build_fold_stats(fold_stats)
    return _assign_rank_signals(result, config)
