"""Stable rank retention, independent of future prices and replay accounting."""

import math


def choose(scores, previous, *, top_n=50, buffer=0):
    if (
        not isinstance(scores, dict)
        or type(top_n) is not int
        or not 1 <= top_n <= 50
        or type(buffer) is not int
        or not 0 <= buffer <= 20
        or len(scores) < top_n
        or not isinstance(previous, list)
        or len(previous) != len(set(previous))
        or any(
            not isinstance(k, str)
            or not k
            or type(v) not in (int, float)
            or not math.isfinite(v)
            for k, v in scores.items()
        )
    ):
        raise ValueError("INVALID_RANKING_POOL")
    if len(set(scores.values())) == 1:
        raise ValueError("CONSTANT_SCORES")
    ranked = sorted(scores, key=lambda name: (-scores[name], name))
    retained = set(previous) & set(ranked[: top_n + buffer])
    selected = [name for name in ranked if name in retained][:top_n]
    selected += [name for name in ranked if name not in retained][
        : top_n - len(selected)
    ]
    return sorted(selected)
