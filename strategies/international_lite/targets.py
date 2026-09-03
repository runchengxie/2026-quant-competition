from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Mapping, Sequence

from packages.contracts import TargetSet

from .features import DailyBar, rank_symbols


def build_target_set(
    strategy_id: str,
    market: str,
    history: Mapping[str, Sequence[DailyBar]],
    *,
    top_k: int,
    lookback: int = 20,
    as_of: str,
) -> TargetSet:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    ranked = rank_symbols(history, lookback=lookback)
    selected = ranked[:top_k]
    if not selected:
        raise ValueError("history must contain at least one symbol")
    weight = Decimal(1) / Decimal(len(selected))
    return TargetSet.from_dict({
        "schema_version": "1.0", "strategy_id": strategy_id, "market": market,
        "as_of": as_of, "targets": [
            {"symbol": symbol, "weight": str(weight)} for symbol, _ in selected
        ],
    })
