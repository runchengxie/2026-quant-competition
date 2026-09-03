from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean, stdev
from typing import Iterable


@dataclass(frozen=True, slots=True)
class CompetitionMetrics:
    cumulative_return: float
    sharpe: float
    max_drawdown: float
    positive_period_fraction: float


def evaluate_competition_metrics(returns: Iterable[float], *, periods_per_year: int = 252) -> CompetitionMetrics:
    values = [float(value) for value in returns]
    if not values or any(not isfinite(value) or value <= -1 for value in values):
        raise ValueError("returns must be finite and greater than -100%")
    equity = 1.0
    peak = 1.0
    drawdowns = []
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdowns.append(1.0 - equity / peak)
    deviation = stdev(values) if len(values) > 1 else 0.0
    sharpe = mean(values) / deviation * sqrt(periods_per_year) if deviation else 0.0
    return CompetitionMetrics(
        cumulative_return=equity - 1.0,
        sharpe=sharpe,
        max_drawdown=max(drawdowns, default=0.0),
        positive_period_fraction=sum(value > 0 for value in values) / len(values),
    )
