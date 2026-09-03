from decimal import Decimal

from apps.execution_runner.runner import ExecutionCandidate
from packages.execution_policies.rebalance import plan_rebalance


def test_plan_rebalance_emits_buy_and_sell_deltas():
    intents = plan_rebalance(
        (
            ExecutionCandidate("0700.HK", Decimal("10"), Decimal("10")),
            ExecutionCandidate("0005.HK", Decimal("2"), Decimal("2")),
        ),
        {"0700.HK": Decimal("4"), "0005.HK": Decimal("5")},
    )
    assert [(i.symbol, i.side, i.quantity) for i in intents] == [
        ("0700.HK", "BUY", Decimal("6")),
        ("0005.HK", "SELL", Decimal("3")),
    ]


def test_plan_rebalance_is_empty_when_positions_match():
    assert plan_rebalance(
        (ExecutionCandidate("0700.HK", Decimal("10"), Decimal("10")),),
        {"0700.HK": Decimal("10")},
    ) == ()
