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
class HKBacktestConfig:
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    lookbacks: tuple[int, ...] = (126, 252)
    momentum_weights: tuple[float, ...] = (0.5, 0.3)
    volatility_window: int = 60
    top_k: int = 10
    max_weight: float = 0.12
    cash_weight: float = 0.02
    mode: str = "momentum_volatility"

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions must be non-negative")
        if not self.lookbacks or any(window < 1 for window in self.lookbacks):
            raise ValueError("lookbacks must be positive")
        if len(self.momentum_weights) != len(self.lookbacks) or any(weight < 0 for weight in self.momentum_weights):
            raise ValueError("momentum_weights must match lookbacks and be non-negative")
        if self.volatility_window < 2 or self.top_k < 1:
            raise ValueError("volatility_window and top_k must be positive")
        if not 0 < self.max_weight <= 1 or not 0 <= self.cash_weight < 1:
            raise ValueError("weights are out of range")
        if self.mode not in {"pure_momentum", "momentum_volatility"}:
            raise ValueError("unsupported mode")


@dataclass(frozen=True, slots=True)
class RebalanceRecord:
    date: str
    as_of: str
    symbols: tuple[str, ...]
    turnover: float


@dataclass(frozen=True, slots=True)
class HKBacktestResult:
    dates: tuple[str, ...]
    portfolio_returns: tuple[float, ...]
    benchmark_returns: tuple[float, ...]
    turnover: tuple[float, ...]
    rebalances: tuple[RebalanceRecord, ...]
    metrics: CompetitionMetrics
    benchmark_metrics: CompetitionMetrics
    average_turnover: float
    holding_rate: float
    empty_days: int


@dataclass(frozen=True, slots=True)
class RankedSymbol:
    symbol: str
    score: float


def load_daily_csv(path: str | Path) -> list[DailyBar]:
    rows: list[DailyBar] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                trading_date = str(row["date"])
                close = float(row["close"])
                volume = float(row.get("volume", 0) or 0)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid daily row or close in {path}") from exc
            if not trading_date or close <= 0:
                raise ValueError(f"close must be positive in {path}")
            rows.append(DailyBar(trading_date, close, volume))
    if not rows:
        raise ValueError(f"no daily rows in {path}")
    return sorted(rows, key=lambda item: item.date)


def _aligned(history: Sequence[DailyBar]) -> dict[str, DailyBar]:
    return {bar.date: bar for bar in history}


def _zscore(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    center = mean(values.values())
    deviation = pstdev(values.values())
    if deviation == 0:
        return {symbol: 0.0 for symbol in values}
    return {symbol: (value - center) / deviation for symbol, value in values.items()}


def _target_weights(ranked: Sequence[tuple[str, float]], config: HKBacktestConfig) -> dict[str, float]:
    selected = [symbol for symbol, _ in ranked[: config.top_k]]
    investable = 1.0 - config.cash_weight
    raw = investable / len(selected)
    weight = min(raw, config.max_weight)
    weights = {symbol: weight for symbol in selected}
    residual = investable - sum(weights.values())
    for symbol in selected:
        if residual <= 1e-12:
            break
        add = min(config.max_weight - weights[symbol], residual)
        weights[symbol] += add
        residual -= add
    return weights


def rank_symbols(
    history: Mapping[str, Sequence[DailyBar]],
    as_of: str,
    *,
    lookbacks: tuple[int, ...] = (126, 252),
    momentum_weights: tuple[float, ...] | None = None,
    volatility_window: int = 60,
    mode: str = "momentum_volatility",
) -> list[RankedSymbol]:
    weights = momentum_weights if momentum_weights is not None else ((1.0,) if len(lookbacks) == 1 else (0.5, 0.3))
    config = HKBacktestConfig(
        lookbacks=lookbacks,
        momentum_weights=weights,
        volatility_window=volatility_window,
        mode=mode,
    )
    return [RankedSymbol(symbol, score) for symbol, score in _rank(history, as_of, config)]


def select_targets(
    ranked: Sequence[RankedSymbol],
    *,
    top_k: int = 10,
    max_weight: float = 0.12,
    cash_weight: float = 0.02,
) -> dict[str, float]:
    config = HKBacktestConfig(top_k=top_k, max_weight=max_weight, cash_weight=cash_weight)
    return _target_weights([(item.symbol, item.score) for item in ranked], config)


def _rank(history: Mapping[str, Sequence[DailyBar]], as_of: str, config: HKBacktestConfig) -> list[tuple[str, float]]:
    momentum_windows = sorted(config.lookbacks)
    momentum: dict[int, dict[str, float]] = {window: {} for window in momentum_windows}
    volatility: dict[str, float] = {}
    for symbol, bars in history.items():
        usable = [bar for bar in bars if bar.date <= as_of]
        closes = [bar.close for bar in usable]
        required = max(max(momentum_windows), config.volatility_window) + 1
        if len(closes) < required:
            continue
        for window in momentum_windows:
            momentum[window][symbol] = closes[-1] / closes[-window - 1] - 1.0
        returns = [closes[i] / closes[i - 1] - 1.0 for i in range(len(closes) - config.volatility_window, len(closes))]
        volatility[symbol] = pstdev(returns)
    if not volatility:
        return []
    components = []
    for window in momentum_windows:
        components.append(_zscore(momentum[window]))
    volatility_z = _zscore(volatility)
    ranked = []
    for symbol in sorted(volatility):
        score = sum(weight * components[index].get(symbol, 0.0) for index, weight in enumerate(config.momentum_weights))
        if config.mode == "momentum_volatility":
            score -= 0.2 * volatility_z.get(symbol, 0.0)
        ranked.append((symbol, score))
    return sorted(ranked, key=lambda item: (item[1], item[0]), reverse=True)


def run_monthly_backtest(
    history: Mapping[str, Sequence[DailyBar]],
    benchmark: Sequence[DailyBar],
    config: HKBacktestConfig,
) -> HKBacktestResult:
    if not history:
        raise ValueError("universe must not be empty")
    benchmark_by_date = _aligned(benchmark)
    if len(benchmark_by_date) < 2:
        raise ValueError("benchmark must have at least two rows")
    symbol_dates = {symbol: _aligned(bars) for symbol, bars in history.items()}
    dates = sorted(set(benchmark_by_date).intersection(*(set(values) for values in symbol_dates.values())))
    if len(dates) < 2:
        raise ValueError("universe and benchmark have insufficient overlap")
    warmup = max(max(config.lookbacks), config.volatility_window) + 1
    active: dict[str, float] = {}
    portfolio_returns: list[float] = []
    benchmark_returns: list[float] = []
    output_dates: list[str] = []
    turnovers: list[float] = []
    rebalances: list[RebalanceRecord] = []
    previous_date = dates[0]
    previous_month = previous_date[:7]
    for current_date in dates[1:]:
        prior_month = previous_date[:7]
        if current_date[:7] != prior_month and dates.index(previous_date) >= warmup:
            ranked = _rank(history, previous_date, config)
            target = _target_weights(ranked, config) if ranked else {}
            turnover = sum(abs(target.get(symbol, 0.0) - active.get(symbol, 0.0)) for symbol in set(target) | set(active))
            active = target
            turnovers.append(turnover)
            rebalances.append(RebalanceRecord(current_date, previous_date, tuple(target), turnover))
        if active:
            day_return = sum(weight * (symbol_dates[symbol][current_date].close / symbol_dates[symbol][previous_date].close - 1.0) for symbol, weight in active.items())
            day_return -= (config.commission_bps + config.slippage_bps) / 10_000.0 * (turnovers[-1] if rebalances and rebalances[-1].date == current_date else 0.0)
            portfolio_returns.append(day_return)
            benchmark_returns.append(benchmark_by_date[current_date].close / benchmark_by_date[previous_date].close - 1.0)
            output_dates.append(current_date)
        previous_date = current_date
    if not portfolio_returns:
        raise ValueError("insufficient history for first monthly signal")
    metrics = evaluate_competition_metrics(portfolio_returns)
    benchmark_metrics = evaluate_competition_metrics(benchmark_returns)
    average_turnover = sum(turnovers) / len(turnovers) if turnovers else 0.0
    return HKBacktestResult(tuple(output_dates), tuple(portfolio_returns), tuple(benchmark_returns), tuple(turnovers), tuple(rebalances), metrics, benchmark_metrics, average_turnover, 1.0, 0)
