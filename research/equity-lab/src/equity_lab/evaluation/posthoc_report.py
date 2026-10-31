"""Versioned supplied-file diagnostic report, independent of research runners."""

import math

from .posthoc_diagnostics import daily_diagnostic, forward_label
from .posthoc_statistics import holm, uncertainty


def evaluate(evidence, family):
    if (
        set(evidence)
        != {
            "schema",
            "calendar",
            "cohorts",
            "observations",
            "blocks",
            "original_labels",
        }
        or evidence["schema"] != "equity.posthoc_inputs.v1"
    ):
        raise ValueError("INVALID_POSTHOC_INPUTS")
    calendar, cohorts, blocks = (evidence[k] for k in ("calendar", "cohorts", "blocks"))
    if calendar != sorted(set(calendar)) or not calendar:
        raise ValueError("INVALID_POSTHOC_CALENDAR")
    if len(blocks) != 16 or len({b["id"] for b in blocks}) != 16:
        raise ValueError("INVALID_POSTHOC_BLOCKS")
    expected = [dict(block=b["id"], horizon=h) for b in blocks for h in (1, 5, 10, 20)]
    if family != expected:
        raise ValueError("POSTHOC_FAMILY_CHANGED")
    observations = {}
    for d, n, ticker, opening, close, valid, action in evidence["observations"]:
        if (
            d not in calendar
            or (d, n) in observations
            or type(valid) is not bool
            or type(action) is not bool
        ):
            raise ValueError("INVALID_POSTHOC_OBSERVATIONS")
        observations[d, n] = dict(
            ticker=ticker,
            open=opening,
            close=close,
            valid=valid,
            action_boundary=action,
        )
    for d, names in cohorts.items():
        if d not in calendar or len(set(names)) != len(names):
            raise ValueError("INVALID_POSTHOC_COHORT")
    by_name = {}
    for (d, n), row in observations.items():
        by_name.setdefault(n, {})[d] = row
    labels = {
        (d, n, h): forward_label(calendar, by_name.get(n, {}), d, h)
        for d, names in cohorts.items()
        for n in names
        for h in (1, 5, 10, 20)
    }
    original = {}
    for d, n, h, value in evidence["original_labels"]:
        if (d, n, h) in original:
            raise ValueError("DUPLICATE_ORIGINAL_LABEL")
        original[d, n, h] = value
    if set(original) != {k for k in labels if k[2] in (5, 20)}:
        raise ValueError("ORIGINAL_LABEL_GRID_CHANGED")
    for key, value in original.items():
        actual = labels[key]
        if (actual is None) != (value is None) or (
            actual is not None
            and (
                type(value) not in (float, int)
                or not math.isfinite(value)
                or not math.isclose(actual, value, abs_tol=1e-12, rel_tol=1e-12)
            )
        ):
            raise ValueError("ORIGINAL_LABEL_MISMATCH")
    rows = []
    for block in blocks:
        sessions = block["sessions"]
        keys = {(d, n) for d in sessions for n in cohorts.get(d, [])}
        scores = {}
        for d, n, score in block["scores"]:
            if (d, n) in scores or (d, n) not in keys:
                raise ValueError("POSTHOC_SCORE_GRID_CHANGED")
            if score is not None and (
                type(score) not in (int, float) or not math.isfinite(score)
            ):
                raise ValueError("INVALID_POSTHOC_SCORE")
            scores[d, n] = score
        if set(scores) != keys or any(d not in cohorts for d in sessions):
            raise ValueError("POSTHOC_SCORE_GRID_CHANGED")
        for h in (1, 5, 10, 20):
            daily = [
                dict(
                    date=d,
                    **daily_diagnostic(
                        [scores[d, n] for n in cohorts[d]],
                        [labels[d, n, h] for n in cohorts[d]],
                    ),
                )
                for d in sessions
            ]
            ics = [r["rank_ic"] for r in daily if r["rank_ic"] is not None]
            rows.append(
                dict(
                    block=block["id"],
                    horizon=h,
                    daily=daily,
                    valid_ic_sessions=len(ics),
                    mean_daily_ic=math.fsum(ics) / len(ics) if ics else None,
                    uncertainty=uncertainty(
                        [r["rank_ic"] for r in daily], h, sessions, calendar
                    ),
                    holm_p=None,
                )
            )
    adjusted = holm([r["uncertainty"]["p"] for r in rows])
    for row, p in zip(rows, adjusted, strict=True):
        row["holm_p"] = p
    return dict(
        schema="equity.posthoc_diagnostics.v1",
        status="completed",
        history="POSTHOC_EXPOSED_HISTORY",
        formal_performance_ready=False,
        scientific_requirements="all_six_remain_blocked",
        estimand="equal_session_mean_cross_sectional_rank_ic",
        family_size=64,
        correction_scope="declared_64_only_not_adaptive_search",
        quintiles="descriptive_forward_raw_returns_not_investable_pnl_outside_family",
        original_5_20_labels_verified=True,
        hypotheses=rows,
    )
