from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: Decimal
    limit_price: Decimal | None
    order_type: str

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if self.order_type not in {"market", "limit"}:
            raise ValueError("order_type must be market or limit")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    intent: OrderIntent
    slice_index: int = 0
    slices: int = 1
    dry_run: bool = False

    @property
    def quantity(self) -> Decimal:
        return self.intent.quantity


def plan_single_order(intent: OrderIntent) -> tuple[OrderIntent, ...]:
    if intent.order_type == "market" and intent.limit_price is not None:
        raise ValueError("market orders must not set limit_price")
    if intent.order_type == "limit" and intent.limit_price is None:
        raise ValueError("limit orders require limit_price")
    return (intent,)


def plan_twap(intent: OrderIntent, *, slices: int) -> tuple[PlannedOrder, ...]:
    if slices < 1:
        raise ValueError("slices must be positive")
    plan_single_order(intent)
    base, remainder = divmod(intent.quantity, Decimal(slices))
    if base <= 0:
        raise ValueError("slices cannot exceed quantity")
    return tuple(
        PlannedOrder(
            intent=replace(intent, quantity=base + (Decimal("1") if i < remainder else Decimal("0"))),
            slice_index=i,
            slices=slices,
            dry_run=True,
        )
        for i in range(slices)
    )
