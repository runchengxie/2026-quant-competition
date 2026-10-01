from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

OrderSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class OrderIntent:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
