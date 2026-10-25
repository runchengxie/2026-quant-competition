import copy

import pytest

from competition_tools.evaluation.holding_reference import (
    verify_holding_account,
    verify_plans,
)


def fixture():
    calendar = [f"2026-01-0{i}" for i in range(1, 5)]
    observations = {
        (d, "A"): dict(open=100.0, close=100.0, valid=True) for d in calendar
    }
    plans = [dict(date=calendar[0], selected=["A"], reason=None)]
    actual = dict(
        status="completed",
        reason=None,
        blocked_date=None,
        requested_dates=3,
        valid_dates=3,
        metrics=dict(net_return=0.0, max_drawdown=0.0, total_costs=0.0, turnover=2.0),
        periods=[],
        accounting_model="raw_open_holding_cash.v1",
        currency="USD",
        formal_performance_ready=False,
    )
    for i, d in enumerate(calendar[1:]):
        cash = 0.0 if i == 0 else 1.0
        actual["periods"].append(
            dict(
                date=d,
                equity=1.0,
                cash=cash,
                quantities={"A": 0.01} if i == 0 else {},
                positions={"A": 1.0} if i == 0 else {},
                trade_cost=0.0,
                liquidation_cost=0.0,
                cost=0.0,
                price_pnl=0.0,
                turnover=1.0 if i < 2 else 0.0,
                net_return=0.0,
            )
        )
    return calendar, observations, plans, actual


def test_independent_cash_reference_accepts_marked_holdings_and_terminal_exit():
    calendar, observations, plans, actual = fixture()
    verify_holding_account(
        actual,
        observations,
        calendar,
        calendar[:2],
        plans,
        horizon=2,
        fee_bps=0,
        delay=0,
    )


def test_changed_terminal_cash_or_held_quantity_is_rejected():
    calendar, observations, plans, actual = fixture()
    for mutate in [
        lambda x: x["periods"][1].update(cash=0.9),
        lambda x: x["periods"][0]["quantities"].update(A=0.02),
    ]:
        changed = copy.deepcopy(actual)
        mutate(changed)
        with pytest.raises(ValueError):
            verify_holding_account(
                changed,
                observations,
                calendar,
                calendar[:2],
                plans,
                horizon=2,
                fee_bps=0,
                delay=0,
            )


def test_reference_requires_missing_price_block_at_first_gap():
    calendar, observations, plans, actual = fixture()
    del observations[(calendar[2], "A")]
    with pytest.raises(ValueError):
        verify_holding_account(
            actual,
            observations,
            calendar,
            calendar[:2],
            plans,
            horizon=2,
            fee_bps=0,
            delay=0,
        )
    actual.update(
        status="blocked",
        reason="MISSING_HELD_OR_SELECTED_PRICE",
        blocked_date=calendar[2],
        metrics=None,
        valid_dates=1,
        periods=actual["periods"][:1],
    )
    verify_holding_account(
        actual,
        observations,
        calendar,
        calendar[:2],
        plans,
        horizon=2,
        fee_bps=0,
        delay=0,
    )


def test_independent_reference_requires_known_action_quarantine():
    calendar, observations, plans, actual = fixture()
    observations[(calendar[2], "A")]["action_boundary"] = True
    with pytest.raises(ValueError):
        verify_holding_account(
            actual,
            observations,
            calendar,
            calendar[:2],
            plans,
            horizon=2,
            fee_bps=0,
            delay=0,
        )


def test_independent_selection_rejects_future_outcome_filtered_pool():
    pool = {
        "2026-01-01": {
            f"S{i:02}": {"valid": True, "session_return": i / 100} for i in range(55)
        }
    }
    chosen = [f"S{i:02}" for i in range(50)]
    plans = [dict(date="2026-01-01", selected=chosen, reason=None)]
    verify_plans(plans, pool, None, ["2026-01-01"], 5, "reversal", 0)
    plans[0]["selected"] = [f"S{i:02}" for i in range(1, 51)]
    with pytest.raises(ValueError):
        verify_plans(plans, pool, None, ["2026-01-01"], 5, "reversal", 0)
