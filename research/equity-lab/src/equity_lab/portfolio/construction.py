"""Long-only weight policies, independent of replay and return accounting.

Inputs use the engine's date/code grid. These policies preserve the legacy
score priority, cash retention, identifier tie-break and target-weight turnover
conventions. They do not model orders, fills or drifted holding quantities.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd


class WeightConstraints(Protocol):
    """Structural input accepted by weight construction, including BacktestConfig."""

    max_positions: int | None
    max_single_name_weight: float | None
    max_gross_exposure: float | None


def _clean_non_negative_series(values: pd.Series) -> pd.Series:
    return (
        pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0.0).astype(float)
    )


def _select_top_positions(
    df: pd.DataFrame,
    scores: pd.Series,
    max_positions: int | None,
) -> pd.Series:
    if max_positions is None:
        return scores

    limit = int(max_positions)
    if limit <= 0:
        return pd.Series(0.0, index=df.index, dtype=float)

    selected = pd.Series(False, index=df.index)
    ranking_frame = df[["date", "code"]].copy()
    ranking_frame["_score"] = scores

    for _, group in ranking_frame[ranking_frame["_score"] > 0].groupby(
        "date", sort=False
    ):
        keep_index = (
            group.sort_values(["_score", "code"], ascending=[False, True])
            .head(limit)
            .index
        )
        selected.loc[keep_index] = True

    return scores.where(selected, 0.0)


def _normalize_scores_by_date(scores: pd.Series, dates: pd.Series) -> pd.Series:
    totals = scores.groupby(dates).transform("sum")
    return scores.where(totals <= 0, scores / totals).where(totals > 0, 0.0)


def build_raw_weights(df: pd.DataFrame, config: WeightConstraints) -> pd.Series:
    if "precomputed_weight" in df.columns:
        scores = _clean_non_negative_series(df["precomputed_weight"])
        return _select_top_positions(df, scores, config.max_positions)

    if "weight_score" in df.columns:
        scores = _clean_non_negative_series(df["weight_score"])
        scores = _select_top_positions(df, scores, config.max_positions)
        return _normalize_scores_by_date(scores, df["date"])

    scores = _clean_non_negative_series(df["signal"])
    scores = _select_top_positions(df, scores, config.max_positions)
    return _normalize_scores_by_date(scores, df["date"])


def apply_static_weight_limits(
    weights: pd.Series, dates: pd.Series, config: WeightConstraints
) -> pd.Series:
    limited = weights.fillna(0.0).clip(lower=0.0)

    if config.max_single_name_weight is not None:
        max_weight = max(float(config.max_single_name_weight), 0.0)
        limited = limited.clip(upper=max_weight)

    if config.max_gross_exposure is not None:
        max_gross = max(float(config.max_gross_exposure), 0.0)
        gross = limited.groupby(dates).transform("sum")
        scale = pd.Series(1.0, index=limited.index, dtype=float)
        mask = gross > max_gross
        scale.loc[mask] = np.where(
            gross.loc[mask] > 0.0, max_gross / gross.loc[mask], 0.0
        )
        limited = limited * scale

    return limited.fillna(0.0)


def apply_daily_turnover_limit(
    df: pd.DataFrame,
    desired_target_weight: pd.Series,
    max_daily_turnover: float | None,
) -> pd.Series:
    if max_daily_turnover is None:
        return desired_target_weight.fillna(0.0)

    limit = max(float(max_daily_turnover), 0.0)
    target_weight = pd.Series(0.0, index=df.index, dtype=float)
    previous_by_code = {str(code): 0.0 for code in df["code"].astype(str).unique()}

    for _, group in df.groupby("date", sort=True):
        previous = group["code"].astype(str).map(previous_by_code).astype(float)
        desired = desired_target_weight.loc[group.index].fillna(0.0).astype(float)
        delta = desired.to_numpy(dtype=float) - previous.to_numpy(dtype=float)
        turnover = float(np.abs(delta).sum())

        if turnover > limit and turnover > 0.0:
            delta = delta * (limit / turnover)

        actual = previous.to_numpy(dtype=float) + delta
        target_weight.loc[group.index] = actual
        for code, value in zip(group["code"].astype(str), actual, strict=True):
            previous_by_code[str(code)] = float(value)

    return target_weight.fillna(0.0)
