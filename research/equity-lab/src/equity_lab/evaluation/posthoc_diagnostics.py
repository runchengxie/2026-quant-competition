"""Pure, future-label-safe fixed-score diagnostics on supplied observations."""

import math

import numpy as np
import pandas as pd


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def daily_diagnostic(scores, labels):
    if len(scores) != len(labels):
        raise ValueError("SCORE_LABEL_SHAPE_MISMATCH")
    available = [
        (float(s), y) for s, y in zip(scores, labels, strict=True) if finite(s)
    ]
    scored = [s for s, y in available]
    pairs = [(s, float(y)) for s, y in available if finite(y)]
    n = len(pairs)
    ic_reason, ic = None, None
    if any(not finite(s) and finite(y) for s, y in zip(scores, labels, strict=True)):
        ic_reason = "missing_predictions"
    elif n < 30:
        ic_reason = "fewer_than_30_candidates"
    elif len({s for s, y in pairs}) < 2 or len({y for s, y in pairs}) < 2:
        ic_reason = "constant_scores_or_labels"
    else:
        ic = float(
            pd.Series([s for s, y in pairs])
            .rank()
            .corr(pd.Series([y for s, y in pairs]).rank())
        )
    edges, reason = None, None
    if len(set(scored)) < 5:
        reason = "fewer_than_five_distinct_scores"
    else:
        cuts = np.quantile(scored, [0.2, 0.4, 0.6, 0.8], method="linear")
        if not np.all(np.diff(cuts) > 0):
            reason = "duplicate_quantile_edges"
        else:
            edges = cuts.tolist()
    groups = [[] for _ in range(5)]
    if edges is not None:
        for score, label in pairs:
            group = next((i for i, edge in enumerate(edges) if score <= edge), 4)
            groups[group].append(label)
    returns = [float(np.mean(g)) if g else None for g in groups]
    return dict(
        cohort=len(scores),
        finite_scores=len(scored),
        valid_labels=n,
        coverage=n / len(scored) if scored else None,
        edges=edges,
        quintile_reason=reason,
        quintile_counts=[len(g) for g in groups],
        quintile_returns=returns,
        top_minus_bottom=(
            returns[4] - returns[0]
            if returns[4] is not None and returns[0] is not None
            else None
        ),
        rank_ic=ic,
        ic_reason=ic_reason,
    )


def forward_label(calendar, observations, day, horizon):
    if type(horizon) is not int or horizon not in (1, 5, 10, 20):
        raise ValueError("INVALID_DECAY_HORIZON")
    index = calendar.index(day)
    future = calendar[index + 1 : index + horizon + 1]
    # The priced interval begins at t+1 open; t OHLC/action is outside it.
    rows = [observations.get(d) for d in future]
    if len(future) != horizon or any(r is None for r in rows):
        return None
    if (
        any(
            not r["valid"]
            or r["action_boundary"]
            or any(not finite(r[p]) or r[p] <= 0 for p in ("open", "close"))
            or not isinstance(r["ticker"], str)
            or r["ticker"].strip() in ("", "nan", "None")
            for r in rows
        )
        or len({r["ticker"] for r in rows}) != 1
    ):
        return None
    value = rows[-1]["close"] / rows[0]["open"] - 1
    return value if finite(value) else None
