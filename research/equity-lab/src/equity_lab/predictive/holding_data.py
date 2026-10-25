"""Calendar-complete raw holding labels; no split or dividend adjustment."""

import numpy as np
import pandas as pd

from .data import prepare_daily


def holding_folds(sessions):
    if sessions != sorted(set(sessions)) or len(sessions) < 227:
        raise ValueError("HOLDING_NEEDS_126_TRAIN_80_TEST_21_FUTURE_SESSIONS")
    dates = sessions[:-21][-80:]
    return [dates[:40], dates[40:]]


def prepare_holding(raw, schedule, horizon):
    if type(horizon) is not int or horizon not in (5, 20):
        raise ValueError("UNSUPPORTED_HOLDING_HORIZON")
    frame = prepare_daily(raw, schedule)
    if "KnownActionBoundary" in raw and not pd.api.types.is_bool_dtype(
        raw.KnownActionBoundary
    ):
        raise ValueError("INVALID_ACTION_BOUNDARY_FLAGS")
    sessions = frame.attrs["sessions"]
    pieces = []
    closes = schedule["close"].copy()
    closes.index = pd.DatetimeIndex(closes.index).strftime("%Y-%m-%d")
    for _, group in frame.groupby("candidate_id", sort=True):
        grid = group.set_index("date").reindex(sessions)
        valid = grid.price_valid.eq(True)
        if "KnownActionBoundary" in grid:
            valid &= ~grid.KnownActionBoundary.eq(True)
        complete = pd.concat(
            [valid.shift(-i, fill_value=False) for i in range(1, horizon + 1)], axis=1
        ).all(axis=1)
        target = (
            grid.close_price.shift(-horizon) / grid.open_price.shift(-1) - 1
        ).where(complete)
        group = group.copy()
        group["target"] = group.date.map(target).to_numpy()
        group["label_end"] = group.date.map(closes.shift(-horizon))
        group["label_reason"] = np.where(
            group.target.notna(), "observed_complete_holding", "missing_holding_session"
        )
        pieces.append(group)
    result = (
        pd.concat(pieces, ignore_index=True)
        .sort_values(["date", "candidate_id"])
        .reset_index(drop=True)
    )
    result.attrs["sessions"] = sessions
    return result
