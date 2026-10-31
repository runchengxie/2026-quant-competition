"""Independent stdlib arithmetic over saved diagnostic evidence (never leaf imports)."""

import math
import random

from .comparison_reference import rank_ic


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def same(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError("POSTHOC_FIELDS_CHANGED")
        for k in expected:
            same(actual[k], expected[k])
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("POSTHOC_SHAPE_CHANGED")
        for a, b in zip(actual, expected, strict=True):
            same(a, b)
    elif expected is None or type(expected) in (str, bool, int):
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError("POSTHOC_VALUE_CHANGED")
    elif not finite(actual) or not math.isclose(
        actual, expected, rel_tol=1e-10, abs_tol=1e-10
    ):
        raise ValueError("POSTHOC_ARITHMETIC_CHANGED")


def percentile(values, p):
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def statistics(values, h, sessions, calendar):
    n, lag, length = len(values), h - 1, max(5, h)
    row = dict(
        n=n,
        lag=lag,
        block_length=length,
        draws=2000,
        seed=20261031,
        status="unavailable",
        reason=None,
        mean=None,
        se=None,
        ci95=None,
        p=None,
        bootstrap95=None,
    )
    start = calendar.index(sessions[0]) if sessions and sessions[0] in calendar else -1
    if start < 0 or sessions != calendar[start : start + n]:
        row["reason"] = "noncontiguous_calendar"
        return row
    if not all(finite(v) for v in values):
        row["reason"] = "missing_or_nonfinite_daily_ic"
        return row
    row["mean"] = mean = math.fsum(values) / n
    if n < max(30, 4 * h, 4 * length):
        row["reason"] = "insufficient_sessions"
        return row
    if len(set(values)) == 1:
        row["reason"] = "constant_daily_ic"
        return row
    errors = [v - mean for v in values]
    gamma = [
        math.fsum(errors[t] * errors[t - k] for t in range(k, n)) / n
        for k in range(lag + 1)
    ]
    variance = (
        gamma[0]
        + 2 * math.fsum((1 - k / (lag + 1)) * gamma[k] for k in range(1, lag + 1))
    ) / (n - 1)
    if not finite(variance) or variance <= 0:
        row["reason"] = "invalid_hac_variance"
        return row
    se = math.sqrt(variance)
    generator = random.Random(20261031)
    boot = []
    for _ in range(2000):
        sample = []
        for _ in range(math.ceil(n / length)):
            s = generator.randrange(n - length + 1)
            sample.extend(values[s : s + length])
        boot.append(math.fsum(sample[:n]) / n)
    row.update(
        status="available",
        se=se,
        ci95=[mean - 1.959963984540054 * se, mean + 1.959963984540054 * se],
        p=math.erfc(abs(mean) / se / math.sqrt(2)),
        bootstrap95=[percentile(boot, p) for p in (0.025, 0.975)],
    )
    return row


def daily(scores, labels):
    pairs = [(s, y) for s, y in zip(scores, labels, strict=True) if finite(s)]
    usable = [(s, y) for s, y in pairs if finite(y)]
    xs, ys = [s for s, y in usable], [y for s, y in usable]
    ic = rank_ic(xs, ys)
    missing = any(
        not finite(s) and finite(y) for s, y in zip(scores, labels, strict=True)
    )
    if missing:
        ic = None
    reason = (
        "missing_predictions"
        if missing
        else "fewer_than_30_candidates"
        if len(xs) < 30
        else ("constant_scores_or_labels" if ic is None else None)
    )
    cuts, qreason = None, None
    if len({s for s, y in pairs}) < 5:
        qreason = "fewer_than_five_distinct_scores"
    else:
        cuts = [percentile([s for s, y in pairs], p) for p in (0.2, 0.4, 0.6, 0.8)]
        if any(a >= b for a, b in zip(cuts, cuts[1:])):
            cuts, qreason = None, "duplicate_quantile_edges"
    buckets = [[] for _ in range(5)]
    if cuts is not None:
        for score, value in usable:
            bucket = sum(score > edge for edge in cuts)
            buckets[bucket].append(value)
    means = [math.fsum(b) / len(b) if b else None for b in buckets]
    return dict(
        cohort=len(scores),
        finite_scores=len(pairs),
        valid_labels=len(usable),
        coverage=len(usable) / len(pairs) if pairs else None,
        edges=cuts,
        quintile_reason=qreason,
        quintile_counts=[len(b) for b in buckets],
        quintile_returns=means,
        top_minus_bottom=means[4] - means[0]
        if means[4] is not None and means[0] is not None
        else None,
        rank_ic=ic,
        ic_reason=reason,
    )


def label(observations, calendar, index, name, h):
    if index + h >= len(calendar):
        return None
    rows = [
        observations.get((calendar[i], name)) for i in range(index + 1, index + h + 1)
    ]
    if any(r is None for r in rows):
        return None
    ticker = rows[0][0]
    if not isinstance(ticker, str) or ticker.strip() in ("", "nan", "None"):
        return None
    for symbol, opening, close, valid, action in rows:
        if (
            symbol != ticker
            or not valid
            or action
            or not all(finite(v) and v > 0 for v in (opening, close))
        ):
            return None
    value = rows[-1][2] / rows[0][1] - 1
    return value if finite(value) else None


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
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError("INVALID_POSTHOC_CALENDAR")
    if len(blocks) != 16 or len({b["id"] for b in blocks}) != 16:
        raise ValueError("INVALID_POSTHOC_BLOCKS")
    if family != [
        dict(block=b["id"], horizon=h) for b in blocks for h in (1, 5, 10, 20)
    ]:
        raise ValueError("POSTHOC_FAMILY_CHANGED")
    observations = {}
    for d, n, *row in evidence["observations"]:
        if (
            d not in calendar
            or (d, n) in observations
            or len(row) != 5
            or any(type(v) is not bool for v in row[-2:])
        ):
            raise ValueError("INVALID_POSTHOC_OBSERVATIONS")
        observations[d, n] = row
    for d, names in cohorts.items():
        if d not in calendar or len(set(names)) != len(names):
            raise ValueError("INVALID_POSTHOC_COHORT")
    labels = {
        (d, n, h): label(observations, calendar, calendar.index(d), n, h)
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
    for key, actual in original.items():
        try:
            same(actual, labels[key])
        except ValueError:
            raise ValueError("ORIGINAL_LABEL_MISMATCH") from None
    hypotheses = []
    for block in blocks:
        days = block["sessions"]
        keys = {(d, n) for d in days for n in cohorts.get(d, [])}
        scores = {}
        for d, n, v in block["scores"]:
            if (
                (d, n) not in keys
                or (d, n) in scores
                or (v is not None and not finite(v))
            ):
                raise ValueError("POSTHOC_SCORE_GRID_CHANGED")
            scores[d, n] = v
        if set(scores) != keys or any(d not in cohorts for d in days):
            raise ValueError("POSTHOC_SCORE_GRID_CHANGED")
        for h in (1, 5, 10, 20):
            rows = [
                dict(
                    date=d,
                    **daily(
                        [scores[d, n] for n in cohorts[d]],
                        [labels[d, n, h] for n in cohorts[d]],
                    ),
                )
                for d in days
            ]
            ics = [r["rank_ic"] for r in rows if r["rank_ic"] is not None]
            hypotheses.append(
                dict(
                    block=block["id"],
                    horizon=h,
                    daily=rows,
                    valid_ic_sessions=len(ics),
                    mean_daily_ic=math.fsum(ics) / len(ics) if ics else None,
                    uncertainty=statistics(
                        [r["rank_ic"] for r in rows], h, days, calendar
                    ),
                    holm_p=None,
                )
            )
    ordered = sorted(
        hypotheses,
        key=lambda r: r["uncertainty"]["p"] if r["uncertainty"]["p"] is not None else 1,
    )
    bound = 0.0
    for i, row in enumerate(ordered):
        p = row["uncertainty"]["p"]
        bound = min(1.0, max(bound, (64 - i) * (p if p is not None else 1)))
        if p is not None:
            row["holm_p"] = bound
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
        hypotheses=hypotheses,
    )
