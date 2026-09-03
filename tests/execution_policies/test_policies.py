from decimal import Decimal

import pytest

from packages.execution_policies import OrderIntent, plan_single_order, plan_twap


def test_single_order_policy_is_deterministic():
    intent = OrderIntent("1321.T", "BUY", Decimal("3"), Decimal("66440"), "limit")
    assert plan_single_order(intent) == (intent,)


def test_market_order_does_not_accept_a_limit_price():
    with pytest.raises(ValueError, match="limit_price"):
        plan_single_order(OrderIntent("1321.T", "BUY", Decimal("1"), Decimal("1"), "market"))


def test_twap_splits_quantity_into_deterministic_child_orders():
    intent = OrderIntent("1321.T", "BUY", Decimal("5"), Decimal("66440"), "limit")
    children = plan_twap(intent, slices=3)
    assert [child.quantity for child in children] == [Decimal("2"), Decimal("2"), Decimal("1")]
    assert [child.slice_index for child in children] == [0, 1, 2]
    assert all(child.dry_run for child in children)


def test_twap_rejects_invalid_slice_count():
    intent = OrderIntent("SGOV.US", "BUY", Decimal("1"), None, "market")
    with pytest.raises(ValueError):
        plan_twap(intent, slices=0)
