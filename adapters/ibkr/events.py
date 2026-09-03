"""Translate IBKR callbacks into stable, broker-neutral execution events."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from apps.execution_runner.runner import ExecutionCandidate
from packages.market_model import normalize_symbol


@dataclass(frozen=True, slots=True)
class OrderEvent:
    order_id: str
    status: str
    filled: Decimal
    remaining: Decimal
    average_fill_price: Decimal


@dataclass(frozen=True, slots=True)
class FillEvent:
    order_id: str
    symbol: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    request_id: str
    code: int
    message: str


@dataclass(frozen=True, slots=True)
class ConnectionEvent:
    status: str
    reason: str = ""


NormalizedEvent = OrderEvent | FillEvent | ErrorEvent | ConnectionEvent


def contract_for_symbol(symbol: str) -> Any:
    """Build an ib_insync Stock contract without importing ib_insync in tests."""

    instrument = normalize_symbol(symbol)
    primary_exchange = "TSEJ" if instrument.market.value == "JP" else "ARCA"
    try:
        from ib_insync import Stock
    except ImportError:
        return _ContractShape(
            symbol=instrument.symbol.removesuffix(".T").removesuffix(".US"),
            exchange="SMART",
            currency=instrument.currency.value,
            primaryExchange=primary_exchange,
        )
    return Stock(
        instrument.symbol.rsplit(".", 1)[0],
        "SMART",
        instrument.currency.value,
        primaryExchange=primary_exchange,
    )


@dataclass(frozen=True, slots=True)
class _ContractShape:
    symbol: str
    exchange: str
    currency: str
    primaryExchange: str


def normalize_ibkr_event(raw: Any) -> NormalizedEvent:
    kind = _get(raw, "kind", "")
    if kind == "orderStatus":
        return OrderEvent(
            order_id=str(_get(raw, "orderId", "")),
            status=_normalize_status(str(_get(raw, "status", "unknown"))),
            filled=_decimal(_get(raw, "filled", 0)),
            remaining=_decimal(_get(raw, "remaining", 0)),
            average_fill_price=_decimal(_get(raw, "avgFillPrice", 0)),
        )
    if kind == "execDetails":
        return FillEvent(
            order_id=str(_get(raw, "orderId", "")),
            symbol=str(_get(raw, "symbol", "")),
            quantity=_decimal(_get(raw, "shares", 0)),
            price=_decimal(_get(raw, "price", 0)),
        )
    if kind == "error":
        return ErrorEvent(
            request_id=str(_get(raw, "reqId", "")),
            code=int(_get(raw, "code", 0)),
            message=str(_get(raw, "message", "")),
        )
    if kind in {"connected", "disconnected"}:
        return ConnectionEvent(kind, str(_get(raw, "reason", "")))
    raise ValueError(f"unsupported IBKR event kind: {kind!r}")


class IBKRAdapter:
    """Small adapter boundary; connection/callback wiring is intentionally explicit."""

    def __init__(self, ib: Any, *, allow_submission: bool = False) -> None:
        self.ib = ib
        self.allow_submission = allow_submission

    def submit(self, candidates: tuple[ExecutionCandidate, ...]) -> None:
        if not self.allow_submission or self.ib is None:
            raise RuntimeError("IBKR submission is disabled")
        for candidate in candidates:
            if candidate.quantity is None:
                raise ValueError(f"quantity is required for {candidate.symbol}")
            contract = contract_for_symbol(candidate.symbol)
            order = self._market_order("BUY", candidate.quantity)
            self.ib.placeOrder(contract, order)

    @staticmethod
    def _market_order(action: str, quantity: Decimal) -> Any:
        try:
            from ib_insync import MarketOrder
        except ImportError as exc:
            raise RuntimeError("ib_insync is required for IBKR submission") from exc
        return MarketOrder(action, float(quantity))


def _get(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _normalize_status(value: str) -> str:
    return {
        "Submitted": "submitted",
        "PreSubmitted": "pending",
        "Filled": "filled",
        "Cancelled": "cancelled",
        "ApiCancelled": "cancelled",
        "Inactive": "inactive",
    }.get(value, value.lower())
