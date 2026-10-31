"""Fixed retrospective daily RankIC diagnostics; no discovery or promotion claims."""

import math
import random

import numpy as np

SEED = 20261031
DRAWS = 2000
Z95 = 1.959963984540054


def bootstrap_means(values, length, starts):
    """Non-circular blocks; concatenate ceil(n/length) starts and truncate to n."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if not n or not 1 <= length <= n or not np.isfinite(x).all():
        raise ValueError("INVALID_BOOTSTRAP_INPUT")
    result = []
    for draw in starts:
        if len(draw) != math.ceil(n / length) or any(
            type(s) is not int or not 0 <= s <= n - length for s in draw
        ):
            raise ValueError("INVALID_BOOTSTRAP_STARTS")
        sample = np.concatenate([x[s : s + length] for s in draw])[:n]
        result.append(float(sample.mean()))
    return result


def uncertainty(values, horizon, sessions, calendar):
    if type(horizon) is not int or horizon not in (1, 5, 10, 20):
        raise ValueError("INVALID_DECAY_HORIZON")
    if len(values) != len(sessions) or len(set(calendar)) != len(calendar):
        raise ValueError("INVALID_STATISTICAL_GRID")
    n, lag, length = len(values), horizon - 1, max(5, horizon)
    row = dict(
        n=n,
        lag=lag,
        block_length=length,
        draws=DRAWS,
        seed=SEED,
        status="unavailable",
        reason=None,
        mean=None,
        se=None,
        ci95=None,
        p=None,
        bootstrap95=None,
    )
    positions = {d: i for i, d in enumerate(calendar)}
    indices = [positions.get(d, -1) for d in sessions]
    if not n or indices[0] < 0 or indices != list(range(indices[0], indices[0] + n)):
        row["reason"] = "noncontiguous_calendar"
        return row
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        row["reason"] = "missing_or_nonfinite_daily_ic"
        return row
    x = np.array(values, dtype=float)
    row["mean"] = float(x.mean())
    if n < 30 or n < 4 * (lag + 1) or n < 4 * length:
        row["reason"] = "insufficient_sessions"
        return row
    if np.ptp(x) == 0:
        row["reason"] = "constant_daily_ic"
        return row
    z = x - x.mean()
    covariance = float(z @ z)
    for k in range(1, lag + 1):
        covariance += 2 * (1 - k / (lag + 1)) * float(z[k:] @ z[:-k])
    variance = covariance / (n * (n - 1))
    if not math.isfinite(variance) or variance <= 0:
        row["reason"] = "invalid_hac_variance"
        return row
    se = math.sqrt(variance)
    rng = random.Random(SEED)
    starts = [
        [rng.randrange(n - length + 1) for _ in range(math.ceil(n / length))]
        for _ in range(DRAWS)
    ]
    boot = bootstrap_means(values, length, starts)
    row.update(
        status="available",
        se=se,
        ci95=[row["mean"] - Z95 * se, row["mean"] + Z95 * se],
        p=math.erfc(abs(row["mean"]) / se / math.sqrt(2)),
        bootstrap95=np.quantile(boot, [0.025, 0.975], method="linear").tolist(),
    )
    return row


def holm(pvalues):
    """Complete frozen family; unavailable entries pad correction with p=1."""
    if any(
        p is not None
        and (type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1)
        for p in pvalues
    ):
        raise ValueError("INVALID_HOLM_PVALUE")
    order = sorted(
        range(len(pvalues)), key=lambda i: 1 if pvalues[i] is None else pvalues[i]
    )
    adjusted, previous = [None] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        previous = min(
            1.0,
            max(
                previous,
                (len(order) - rank) * (1 if pvalues[i] is None else pvalues[i]),
            ),
        )
        if pvalues[i] is not None:
            adjusted[i] = previous
    return adjusted
