from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from uuid import uuid4

from apps.execution_runner.runner import ExecutionCandidate
from packages.contracts.orders import OrderIntent


def plan_rebalance(
    targets: Sequence[ExecutionCandidate],
    positions: Mapping[str, Decimal],
) -> tuple[OrderIntent, ...]:
    """Convert target quantities and current positions into signed deltas."""
    intents: list[OrderIntent] = []
    for target in targets:
        if target.quantity is None:
            raise ValueError(f"quantity is required for {target.symbol}")
        current = Decimal(str(positions.get(target.symbol, Decimal("0"))))
        delta = target.quantity - current
        if delta == 0:
            continue
        intents.append(OrderIntent(
            order_id=str(uuid4()), symbol=target.symbol,
            side="BUY" if delta > 0 else "SELL", quantity=abs(delta),
        ))
    return tuple(intents)
