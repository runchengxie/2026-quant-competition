from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DailyBar:
    date: str
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    momentum: float
    volatility: float
    average_volume: float
    score: float


def compute_features(bars: Sequence[DailyBar], *, lookback: int = 20) -> FeatureSnapshot:
    if lookback < 1 or len(bars) <= lookback:
        raise ValueError("need more than lookback daily bars")
    closes = [float(item.close) for item in bars]
    if any(value <= 0 for value in closes):
        raise ValueError("close prices must be positive")
    momentum = closes[-1] / closes[-lookback - 1] - 1.0
    returns = [log(closes[i] / closes[i - 1]) for i in range(len(closes) - lookback, len(closes))]
    mean = sum(returns) / len(returns)
    volatility = sqrt(sum((value - mean) ** 2 for value in returns) / len(returns))
    average_volume = sum(float(item.volume) for item in bars[-lookback:]) / lookback
    score = momentum / max(volatility, 1e-12)
    return FeatureSnapshot(momentum, volatility, average_volume, score)


def rank_symbols(history: Mapping[str, Sequence[DailyBar]], *, lookback: int = 20) -> list[tuple[str, FeatureSnapshot]]:
    ranked = [(symbol, compute_features(bars, lookback=lookback)) for symbol, bars in history.items()]
    return sorted(ranked, key=lambda item: (item[1].score, item[1].momentum, item[0]), reverse=True)
