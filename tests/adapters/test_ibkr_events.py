from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters.ibkr import (
    ConnectionEvent,
    ErrorEvent,
    FillEvent,
    IBKRAdapter,
    OrderEvent,
    contract_for_symbol,
    normalize_ibkr_event,
)
from apps.execution_runner.runner import ExecutionCandidate
from decimal import Decimal


def _fake_market_order(action: str, quantity: Decimal) -> SimpleNamespace:
    return SimpleNamespace(action=action, totalQuantity=quantity)


def test_japanese_symbol_maps_to_ibkr_stock_contract() -> None:
    contract = contract_for_symbol("1321.T")
    assert contract.symbol == "1321"
    assert contract.exchange == "SMART"
    assert contract.primaryExchange == "TSEJ"
    assert contract.currency == "JPY"


def test_us_symbol_maps_to_usd_stock_contract() -> None:
    contract = contract_for_symbol("SGOV.US")
    assert contract.symbol == "SGOV"
    assert contract.exchange == "SMART"
    assert contract.currency == "USD"


@pytest.mark.parametrize(
    ("status", "expected"),
    [("Submitted", "submitted"), ("Filled", "filled"), ("Cancelled", "cancelled")],
)
def test_order_status_is_normalized(status: str, expected: str) -> None:
    event = normalize_ibkr_event(
        SimpleNamespace(
            kind="orderStatus",
            orderId=17,
            status=status,
            filled=1,
            remaining=0,
            avgFillPrice=66440.0,
        )
    )
    assert isinstance(event, OrderEvent)
    assert event.order_id == "17"
    assert event.status == expected
    assert event.average_fill_price == Decimal("66440.0")


def test_fill_error_and_disconnect_events_are_normalized() -> None:
    fill = normalize_ibkr_event(
        {"kind": "execDetails", "orderId": 8, "symbol": "1321", "shares": 1, "price": 66440}
    )
    error = normalize_ibkr_event({"kind": "error", "reqId": 8, "code": 201, "message": "rejected"})
    disconnect = normalize_ibkr_event({"kind": "disconnected", "reason": "gateway closed"})

    assert fill == FillEvent("8", "1321", Decimal("1"), Decimal("66440"))
    assert error == ErrorEvent("8", 201, "rejected")
    assert disconnect == ConnectionEvent("disconnected", "gateway closed")


def test_adapter_submit_is_disabled_without_explicit_port() -> None:
    adapter = IBKRAdapter(ib=None, allow_submission=False)
    candidate = ExecutionCandidate("1321.T", Decimal("1"), Decimal("1"))
    with pytest.raises(RuntimeError, match="submission is disabled"):
        adapter.submit((candidate,))


def test_submit_qualifies_contract_before_placing_order() -> None:
    class QualifiedIB:
        def __init__(self):
            self.qualified = []
            self.placed = []

        def qualifyContracts(self, contract):
            self.qualified.append(contract)
            return [SimpleNamespace(
                symbol=contract.symbol,
                exchange=contract.exchange,
                currency=contract.currency,
                primaryExchange=contract.primaryExchange,
                conId=123,
            )]

        def placeOrder(self, contract, order):
            self.placed.append((contract, order))

    ib = QualifiedIB()
    adapter = IBKRAdapter(ib, allow_submission=True)
    adapter._market_order = _fake_market_order
    adapter.submit((ExecutionCandidate("SGOV.US", Decimal("1"), Decimal("100")),))

    assert len(ib.qualified) == 1
    assert ib.placed[0][0].conId == 123


@pytest.mark.parametrize(
    "matches",
    [[], [SimpleNamespace(), SimpleNamespace()]],
    ids=["no-match", "ambiguous-match"],
)
def test_submit_refuses_unqualified_contract(matches) -> None:
    class UnqualifiedIB:
        def qualifyContracts(self, contract):
            return matches

        def placeOrder(self, contract, order):
            raise AssertionError("must not place an order")

    adapter = IBKRAdapter(UnqualifiedIB(), allow_submission=True)
    adapter._market_order = _fake_market_order
    with pytest.raises(RuntimeError, match="could not qualify contract"):
        adapter.submit((ExecutionCandidate("SGOV.US", Decimal("1"), Decimal("100")),))
