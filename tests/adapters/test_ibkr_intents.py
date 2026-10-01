from decimal import Decimal
from types import SimpleNamespace

from adapters.ibkr.events import IBKRAdapter
from packages.contracts.orders import OrderIntent


def _fake_market_order(action, quantity):
    return SimpleNamespace(action=action)


class FakeIB:
    def __init__(self):
        self.orders = []

    def placeOrder(self, contract, order):
        self.orders.append((contract, order))

    def qualifyContracts(self, contract):
        return [contract]


def test_submit_intents_preserves_buy_and_sell_direction():
    ib = FakeIB()
    adapter = IBKRAdapter(ib, allow_submission=True)
    adapter._market_order = _fake_market_order

    adapter.submit_intents((
        OrderIntent("o1", "0700.HK", "BUY", Decimal("100")),
        OrderIntent("o2", "0700.HK", "SELL", Decimal("100")),
    ))

    assert [order.action for _, order in ib.orders] == ["BUY", "SELL"]
