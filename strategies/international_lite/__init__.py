"""Small price/volume-only strategy for markets observable from IBKR."""

from .features import DailyBar, FeatureSnapshot, compute_features, rank_symbols
from .targets import build_target_set
from .data_quality import ContinuityReport, check_daily_continuity
from .evaluation import CompetitionMetrics, evaluate_competition_metrics
from .backtest import BacktestConfig, BacktestResult, run_backtest

__all__ = [
    "BacktestConfig", "BacktestResult", "CompetitionMetrics", "ContinuityReport", "DailyBar", "FeatureSnapshot", "build_target_set",
    "check_daily_continuity", "compute_features", "evaluate_competition_metrics", "rank_symbols", "run_backtest",
]
