"""Inherited demo signal diagnostics, without model fitting or replay.

Daily IC needs three usable rows and nonconstant values. The legacy pooled
fallback is retained when no daily IC exists; it is not an independent daily
factor test. Column priority and status filtering match historical reports.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_ic_metrics(
    signal_df: pd.DataFrame,
) -> tuple[float | None, float | None]:
    if signal_df.empty:
        return None, None

    signal_column = None
    for candidate in (
        "weight_score",
        "cnn_calibrated_probability",
        "cnn_probability",
        "signal",
    ):
        if candidate in signal_df.columns:
            signal_column = candidate
            break
    if "future_return" in signal_df.columns:
        target_column = "future_return"
    elif "target_label" in signal_df.columns:
        target_column = "target_label"
    else:
        target_column = None
    if signal_column is None or target_column is None:
        return None, None

    frame = signal_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[["date", signal_column, target_column]]
    frame["date"] = frame["date"].astype("datetime64[ns]")
    frame["date"] = frame["date"].dt.floor("D")
    frame = frame.dropna(subset=[signal_column, target_column])
    if frame.empty:
        return None, None

    ics: list[float] = []
    rank_ics: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        if len(group) < 3:
            continue
        signal_values = pd.to_numeric(group[signal_column], errors="coerce").astype(
            float
        )
        target_values = pd.to_numeric(group[target_column], errors="coerce").astype(
            float
        )
        valid = signal_values.notna() & target_values.notna()
        signal_valid = signal_values[valid]
        target_valid = target_values[valid]
        if len(signal_valid) < 3:
            continue
        if signal_valid.nunique() < 2 or target_valid.nunique() < 2:
            continue
        ics.append(float(signal_valid.corr(target_valid)))
        rank_ics.append(float(signal_valid.rank().corr(target_valid.rank())))

    if ics:
        return float(np.nanmean(ics)), float(np.nanmean(rank_ics))

    signal_values = pd.to_numeric(frame[signal_column], errors="coerce").astype(float)
    target_values = pd.to_numeric(frame[target_column], errors="coerce").astype(float)
    if len(signal_values) < 3:
        return None, None
    if signal_values.nunique() < 2 or target_values.nunique() < 2:
        return None, None

    return float(signal_values.corr(target_values)), float(
        signal_values.rank().corr(target_values.rank())
    )


def slice_metric_signal(
    signal_df: pd.DataFrame,
    status_mask: str | None = None,
) -> pd.DataFrame:
    if signal_df.empty:
        return signal_df.copy()

    frame = signal_df.copy()
    if status_mask is None:
        return frame

    if "cnn_model_status" not in frame.columns:
        return frame.iloc[0:0].copy()

    return frame[frame["cnn_model_status"] == status_mask].copy()


def compute_hit_rate(signal_df: pd.DataFrame) -> float | None:
    if signal_df.empty:
        return None
    has_signal = signal_df.get("signal")
    has_label = signal_df.get("target_label")
    if has_signal is None or has_label is None:
        return None
    frame = pd.DataFrame({"signal": has_signal, "target_label": has_label}).dropna()
    if frame.empty:
        return None
    signal = pd.to_numeric(frame["signal"], errors="coerce").fillna(0.0)
    label = pd.to_numeric(frame["target_label"], errors="coerce").fillna(0.0)
    total = int((signal > 0.0).sum())
    if total <= 0:
        return None
    return float(((signal > 0.0) & (label > 0.5)).sum() / total)
