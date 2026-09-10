from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Mapping, Sequence

from strategies.international_lite.evaluation import CompetitionMetrics, evaluate_competition_metrics


@dataclass(frozen=True, slots=True)
class DailyBar:
    date: str
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class GlobalETFConfig:
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    lookbacks: tuple[int, ...] = (63, 126, 252)
    momentum_weights: tuple[float, ...] = (0.25, 0.35, 0.40)
    volatility_window: int = 60
    top_k: int = 3
    max_weight: float = 0.45
    cash_weight: float = 0.10
    absolute_momentum_floor: float = 0.0
    mode: str = "defended_rotation"

    def __post_init__(self) -> None:
        if len(self.lookbacks) != len(self.momentum_weights) or not self.lookbacks or any(x < 1 for x in self.lookbacks):
            raise ValueError("lookbacks and momentum_weights must have matching positive values")
        if abs(sum(self.momentum_weights) - 1.0) > 1e-9 or any(x < 0 for x in self.momentum_weights):
            raise ValueError("momentum_weights must be non-negative and sum to one")
        if self.top_k < 1 or self.volatility_window < 2 or not 0 < self.max_weight <= 1:
            raise ValueError("invalid rotation parameters")
        if not 0 <= self.cash_weight < 1 or self.cash_weight + self.max_weight > 1:
            raise ValueError("cash and weight limits are invalid")
        if self.mode not in {"pure_momentum", "defended_rotation"}:
            raise ValueError("unsupported rotation mode")


@dataclass(frozen=True, slots=True)
class Rebalance:
    date: str
    as_of: str
    holdings: tuple[str, ...]
    turnover: float


@dataclass(frozen=True, slots=True)
class GlobalETFResult:
    dates: tuple[str, ...]
    portfolio_returns: tuple[float, ...]
    benchmark_returns: tuple[float, ...]
    turnover: tuple[float, ...]
    holdings: tuple[tuple[str, ...], ...]
    rebalances: tuple[Rebalance, ...]
    metrics: CompetitionMetrics
    benchmark_metrics: CompetitionMetrics


@dataclass(frozen=True, slots=True)
class RankedAsset:
    symbol: str
    score: float
    momentum: float
    volatility: float


def load_daily_csv(path: str | Path) -> list[DailyBar]:
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                item = DailyBar(str(row["date"]), float(row["close"]), float(row.get("volume", 0) or 0))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid ETF daily row in {path}") from exc
            if not item.date or item.close <= 0:
                raise ValueError(f"close must be positive in {path}")
            rows.append(item)
    if not rows:
        raise ValueError(f"no ETF rows in {path}")
    return sorted(rows, key=lambda item: item.date)


def _zscore(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    center = mean(values.values())
    scale = pstdev(values.values())
    return {key: 0.0 if scale == 0 else (value - center) / scale for key, value in values.items()}


def _rank(history: Mapping[str, Sequence[DailyBar]], as_of: str, config: GlobalETFConfig) -> list[RankedAsset]:
    momentum = {window: {} for window in config.lookbacks}
    volatility = {}
    required = max(max(config.lookbacks), config.volatility_window) + 1
    for symbol, bars in history.items():
        closes = [bar.close for bar in bars if bar.date <= as_of]
        if len(closes) < required:
            continue
        for window in config.lookbacks:
            momentum[window][symbol] = closes[-1] / closes[-window - 1] - 1.0
        returns = [closes[i] / closes[i - 1] - 1.0 for i in range(len(closes) - config.volatility_window, len(closes))]
        volatility[symbol] = pstdev(returns)
    momentum_z = [_zscore(momentum[window]) for window in config.lookbacks]
    volatility_z = _zscore(volatility)
    ranked = []
    for symbol in sorted(volatility):
        score = sum(weight * values.get(symbol, 0.0) for weight, values in zip(config.momentum_weights, momentum_z))
        if config.mode == "defended_rotation":
            score -= 0.20 * volatility_z.get(symbol, 0.0)
        total_momentum = sum(weight * momentum[window].get(symbol, 0.0) for weight, window in zip(config.momentum_weights, config.lookbacks))
        ranked.append(RankedAsset(symbol, score, total_momentum, volatility[symbol]))
    return sorted(ranked, key=lambda item: (item.score, item.symbol), reverse=True)


def rank_assets(history, as_of, *, lookbacks=(63, 126, 252), volatility_window=60, mode="defended_rotation"):
    weights = (0.25, 0.35, 0.40) if len(lookbacks) == 3 else tuple(1 / len(lookbacks) for _ in lookbacks)
    config = GlobalETFConfig(lookbacks=tuple(lookbacks), momentum_weights=weights, volatility_window=volatility_window, mode=mode)
    return _rank(history, as_of, config)


def select_assets(ranked, *, top_k=3, max_weight=0.45, cash_weight=0.10):
    config = GlobalETFConfig(top_k=top_k, max_weight=max_weight, cash_weight=cash_weight)
    selected = [item for item in ranked if item.momentum > config.absolute_momentum_floor][:config.top_k]
    if not selected:
        return {}
    investable = 1.0 - config.cash_weight
    weights = {item.symbol: min(config.max_weight, investable / len(selected)) for item in selected}
    residual = investable - sum(weights.values())
    for item in selected:
        if residual <= 1e-12:
            break
        symbol = item.symbol
        add = min(config.max_weight - weights[symbol], residual)
        weights[symbol] += add
        residual -= add
    return weights


def run_monthly_rotation(history: Mapping[str, Sequence[DailyBar]], config: GlobalETFConfig = GlobalETFConfig()) -> GlobalETFResult:
    if not history:
        raise ValueError("ETF history must not be empty")
    aligned = {symbol: {bar.date: bar for bar in bars} for symbol, bars in history.items()}
    dates = sorted(set.intersection(*(set(values) for values in aligned.values())))
    if len(dates) < max(max(config.lookbacks), config.volatility_window) + 3:
        raise ValueError("ETF history has insufficient common dates")
    active = {}
    output_dates, returns, benchmark, turnover, holdings, rebalances = [], [], [], [], [], []
    previous = dates[0]
    warmup = max(max(config.lookbacks), config.volatility_window) + 1
    for index, current in enumerate(dates[1:], start=1):
        if current[:7] != previous[:7] and index - 1 >= warmup:
            ranked = _rank(history, previous, config)
            target = select_assets(ranked, top_k=config.top_k, max_weight=config.max_weight, cash_weight=config.cash_weight)
            traded = sum(abs(target.get(symbol, 0.0) - active.get(symbol, 0.0)) for symbol in set(target) | set(active))
            active = target
            turnover.append(traded)
            rebalances.append(Rebalance(current, previous, tuple(target), traded))
        if active:
            daily = sum(weight * (aligned[symbol][current].close / aligned[symbol][previous].close - 1.0) for symbol, weight in active.items())
            if rebalances and rebalances[-1].date == current:
                daily -= (config.commission_bps + config.slippage_bps) / 10000 * turnover[-1]
            returns.append(daily)
            benchmark.append(sum(aligned[symbol][current].close / aligned[symbol][previous].close - 1.0 for symbol in aligned) / len(aligned))
            output_dates.append(current)
            holdings.append(tuple(active))
        previous = current
    if not returns:
        raise ValueError("no post-warmup portfolio returns")
    return GlobalETFResult(tuple(output_dates), tuple(returns), tuple(benchmark), tuple(turnover), tuple(holdings), tuple(rebalances), evaluate_competition_metrics(returns), evaluate_competition_metrics(benchmark))
