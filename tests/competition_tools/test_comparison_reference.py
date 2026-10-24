"""Independent reference accepts honest gaps and rejects fabricated accounts."""

import copy

import pytest

from competition_tools.evaluation.comparison_reference import (
    verify_equity_account,
    verify_crypto_account,
)


def equity_case():
    fee = 0.002
    factor = 1.1 * (1 - fee) / (1 + fee)
    cost = fee * 2.1 / (1 + fee)
    period = dict(
        date="2026-01-05",
        execution_date="2026-01-06",
        selected=["A"],
        status="completed",
        reason=None,
        net_return=factor - 1,
        equity=factor,
        price_pnl=0.1 / (1 + fee),
        cost=cost,
    )
    account = dict(
        status="completed",
        requested_dates=1,
        valid_dates=1,
        periods=[period],
        accounting_model="intraday_cash_proxy.v1",
        quote_currency="USD",
        pnl_available=False,
        ex_post_diagnostic=True,
        metrics=dict(
            net_return=factor - 1,
            gross_return=0.1,
            cost_drag=1.1 - factor,
            max_drawdown=0,
            total_costs=cost,
            turnover=2.1 / (1 + fee),
            top_asset_positive_price_pnl_share=1.0,
            without_best_five_days_return=0.0,
        ),
    )
    row = dict(arm="equal_weight", fee_bps=20, delay=0)
    context = dict(
        pool={"2026-01-05": {"A": 0.0}},
        observations={("2026-01-06", "A"): 0.1},
        scores=None,
        sessions=["2026-01-05", "2026-01-06"],
        dates=["2026-01-05"],
    )
    return row, account, context


def test_equity_round_trip_reference_checks_cash_math_and_concentration():
    row, account, context = equity_case()
    result = verify_equity_account(row, account, **context)
    assert result["net_return"] == pytest.approx(account["metrics"]["net_return"])
    assert result["top_asset_positive_price_pnl_share"] == 1


@pytest.mark.parametrize(
    "field,bad",
    [("equity", 1.5), ("cost", 0), ("net_return", float("nan")), ("selected", ["B"])],
)
def test_equity_tampering_is_rejected(field, bad):
    row, account, context = equity_case()
    account["periods"][0][field] = bad
    with pytest.raises(ValueError):
        verify_equity_account(row, account, **context)


def test_reference_accepts_missing_outcome_but_never_completed_metrics():
    row, account, context = equity_case()
    context["observations"] = {}
    account.update(status="blocked", valid_dates=0, metrics=None)
    account["periods"] = [
        dict(
            date="2026-01-05",
            execution_date="2026-01-06",
            selected=["A"],
            status="blocked",
            reason="MISSING_SELECTED_OUTCOME",
        )
    ]
    assert verify_equity_account(row, account, **context) is None
    account["metrics"] = {"net_return": 0}
    with pytest.raises(ValueError):
        verify_equity_account(row, account, **context)


def test_reference_retains_high_ranked_missing_outcome_instead_of_switching():
    row, account, context = equity_case()
    names = [f"A{i:02d}" for i in range(51)]
    row["arm"] = "ridge"
    context["pool"] = {"2026-01-05": {n: 0.0 for n in names}}
    context["scores"] = {("2026-01-05", n): float(i) for i, n in enumerate(names)}
    account["periods"][0]["selected"] = names[:50]
    with pytest.raises(ValueError):
        verify_equity_account(row, account, **context)


def test_reference_rejects_changed_crypto_prices_before_accepting_periods():
    # The full real run exercises all independent piecewise-linear accounts.
    bars = dict(dates=["2026-01-01"] * 342, close={"A": [100.0] * 342})
    value = dict(
        prices={"dates": ["wrong"], "close": {}}, targets=[], decision_flags=[]
    )
    with pytest.raises(ValueError):
        verify_crypto_account(
            dict(arm="buy_hold_equal_weight", fee_bps=35, delay=0), value, bars
        )


def test_parent_inputs_remain_unchanged_during_reference():
    row, account, context = equity_case()
    original = copy.deepcopy((row, account, context))
    verify_equity_account(row, account, **context)
    assert (row, account, context) == original


def test_rank_ic_uses_average_ties_and_preserves_undefined_scores():
    from competition_tools.evaluation.comparison_reference import rank_ic

    assert rank_ic(
        [1] * 20 + [2] * 10, [1] * 10 + [2] * 10 + [3] * 10
    ) == pytest.approx(3**0.5 / 2)
    assert rank_ic([1] * 30, list(range(30))) is None
    assert rank_ic([1, 2], [2, 1]) is None
    with pytest.raises(ValueError):
        rank_ic([float("nan")] * 30, list(range(30)))
