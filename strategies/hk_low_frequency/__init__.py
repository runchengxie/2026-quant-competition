"""Low-frequency Hong Kong equity research strategy."""

from .backtest import (
    DailyBar,
    HKBacktestConfig,
    HKBacktestResult,
    RankedSymbol,
    load_daily_csv,
    rank_symbols,
    run_monthly_backtest,
    select_targets,
)

__all__ = [
    "DailyBar",
    "HKBacktestConfig",
    "HKBacktestResult",
    "RankedSymbol",
    "load_daily_csv",
    "rank_symbols",
    "run_monthly_backtest",
    "select_targets",
]
