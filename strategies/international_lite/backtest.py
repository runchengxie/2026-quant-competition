from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .evaluation import CompetitionMetrics, evaluate_competition_metrics


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    holding_rate: float = 1.0
    average_turnover: float = 0.0
    min_holding_rate: float = 0.5
    max_empty_days: int = 10
    empty_days: int = 0

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions must be non-negative")
        if not 0 <= self.holding_rate <= 1:
            raise ValueError("holding_rate must be between 0 and 1")
        if self.average_turnover < 0 or self.empty_days < 0:
            raise ValueError("turnover and empty_days must be non-negative")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    gross_returns: tuple[float, ...]
    net_returns: tuple[float, ...]
    metrics: CompetitionMetrics
    eligible: bool


def run_backtest(returns: Sequence[float], turnover: Sequence[float], config: BacktestConfig) -> BacktestResult:
    if not returns or len(returns) != len(turnover):
        raise ValueError("returns and turnover must be non-empty and equal length")
    cost_rate = (config.commission_bps + config.slippage_bps) / 10_000.0
    net = tuple(float(value) - cost_rate * float(turn) for value, turn in zip(returns, turnover))
    metrics = evaluate_competition_metrics(net)
    eligible = (
        config.holding_rate >= config.min_holding_rate and config.empty_days <= config.max_empty_days
    ) or config.average_turnover >= 1.0
    return BacktestResult(tuple(float(value) for value in returns), net, metrics, eligible)
