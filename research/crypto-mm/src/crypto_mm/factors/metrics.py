"""Rank association and descriptive groups. These are not portfolio returns."""

import math
from statistics import fmean

from .signals import hour


def numbers(values):
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("INVALID_FACTOR_METRIC_NUMBER")


def average_ranks(values):
    numbers(values)
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks, i = [0.0] * len(values), 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for position in order[i:j]:
            ranks[position] = (i + 1 + j) / 2
        i = j
    return ranks


def rank_ic(signal, target, *, minimum):
    numbers(signal)
    numbers(target)
    if len(signal) != len(target) or type(minimum) is not int or minimum < 1:
        raise ValueError("INVALID_FACTOR_METRIC_INPUT")
    n = len(signal)
    reason = (
        "INSUFFICIENT_OBSERVATIONS"
        if n < minimum
        else "CONSTANT_SIGNAL"
        if len(set(signal)) < 2
        else "CONSTANT_TARGET"
        if len(set(target)) < 2
        else None
    )
    if reason:
        return {"value": None, "n": n, "reason": reason}
    x, y = average_ranks(signal), average_ranks(target)
    xm, ym = fmean(x), fmean(y)
    numerator = sum((a - xm) * (b - ym) for a, b in zip(x, y, strict=True))
    denominator = math.sqrt(
        sum((a - xm) ** 2 for a in x) * sum((b - ym) ** 2 for b in y)
    )
    return {
        "value": max(-1.0, min(1.0, numerator / denominator)),
        "n": n,
        "reason": None,
    }


def selected_hour(timestamp, start, horizon, sampling):
    offset = int((hour(timestamp) - hour(start)).total_seconds() / 3600)
    if sampling not in {"all_valid", "non_overlapping"}:
        raise ValueError("INVALID_FACTOR_SAMPLING")
    return sampling == "all_valid" or offset % horizon == 0


def cross_section(signal, target):
    numbers(signal)
    numbers(target)
    if len(signal) != len(target):
        raise ValueError("INVALID_FACTOR_METRIC_INPUT")
    result = {
        "n": len(signal),
        "rank_ic": None,
        "ic_reason": None,
        "group_mean_forward_returns": None,
        "group_counts": None,
        "top_minus_bottom": None,
        "reason": None,
    }
    if len(signal) < 9:
        return result | {"reason": "INSUFFICIENT_UNDERLYINGS"}
    ranks = average_ranks(signal)
    bins = [[], [], []]
    for rank, value in zip(ranks, target, strict=True):
        bins[min(2, int(3 * (rank - 0.5) / len(signal)))].append(value)
    if any(len(group) < 3 for group in bins):
        return result | {"reason": "INSUFFICIENT_GROUP_SIZE"}
    means = [fmean(group) for group in bins]
    ic = rank_ic(signal, target, minimum=9)
    return result | {
        "rank_ic": ic["value"],
        "ic_reason": ic["reason"],
        "group_counts": [len(g) for g in bins],
        "group_mean_forward_returns": means,
        "top_minus_bottom": means[2] - means[0],
    }
