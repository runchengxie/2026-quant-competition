"""Compatibility imports for the existing backtest preparation API.

Implementation lives in equity_lab.data.preparation. Keep these imports while
supported callers use this path; removal requires a separate API migration.
"""

from equity_lab.data.preparation import REQUIRED_MARKET_COLUMNS, prepare_market_panel

__all__ = ["REQUIRED_MARKET_COLUMNS", "prepare_market_panel"]
