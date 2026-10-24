"""Compatibility imports for the existing backtest metrics API.

Implementation lives in equity_lab.evaluation.performance. Keep these imports
while supported callers use this path; removal requires a separate API migration.
"""

from equity_lab.evaluation.performance import (
    compute_backtest_metrics,
    compute_daily_returns,
    compute_drawdown_series,
    compute_sharpe_ratio,
)

__all__ = [
    "compute_backtest_metrics",
    "compute_daily_returns",
    "compute_drawdown_series",
    "compute_sharpe_ratio",
]
