"""Price contribution and modeled cost must reconcile to the existing accounts."""

import copy

import pytest

from competition_tools.evaluation.contributions import (
    explain_self_financing,
    explain_fractional,
)


def cash_account(prices, *, scale=1.0, first_cost=0.0):
    periods, previous = [], 1.0
    for i, day in enumerate(prices["dates"][1:]):
        positions = {
            p: scale / len(prices["close"]) * row[i + 1] / row[0]
            for p, row in prices["close"].items()
        }
        equity = sum(positions.values())
        periods.append(
            dict(
                date=day,
                positions=positions,
                cash=0.0,
                equity=equity,
                cost=first_cost if i == 0 else 0.0,
                net_return=equity / previous - 1,
            )
        )
        previous = equity
    return dict(
        accounting_model="self_financing_daily.v1",
        quote_currency="USDT",
        periods=periods,
    )


def test_cash_ledger_separates_deducted_cost_from_counterfactual_drag():
    prices = dict(
        dates=["2024-01-01", "2024-01-02", "2024-01-03"], close={"A": [100, 110, 99]}
    )
    cost = 1 - 1 / 1.01
    net = cash_account(prices, scale=1 / 1.01, first_cost=cost)
    gross = cash_account(prices)
    value = explain_self_financing(prices, net, gross)
    assert value["modeled_costs"] == pytest.approx(cost)
    assert value["net_pnl"] == pytest.approx(0.99 / 1.01 - 1)
    assert value["counterfactual_cost_drag_return"] == pytest.approx(0.99 - 0.99 / 1.01)
    assert value["counterfactual_cost_drag_return"] != pytest.approx(
        value["modeled_costs"]
    )
    assert value["price_pnl"] - value["modeled_costs"] == pytest.approx(
        value["net_pnl"]
    )
    assert value["reconciled"] is True


def test_two_asset_contributions_keep_positive_and_negative_values():
    prices = dict(
        dates=["2024-01-01", "2024-01-02"], close={"A": [100, 110], "B": [100, 95]}
    )
    account = cash_account(prices)
    value = explain_self_financing(prices, account, account)
    assert {
        r["instrument"]: r["price_pnl"] for r in value["instruments"]
    } == pytest.approx({"A": 0.05, "B": -0.025})
    assert value["net_return"] == pytest.approx(0.025)


def test_uninvested_cash_has_zero_price_contribution():
    prices = dict(dates=["2024-01-01", "2024-01-02"], close={"A": [100, 110]})
    account = dict(
        accounting_model="self_financing_daily.v1",
        quote_currency="USDT",
        periods=[
            dict(
                date="2024-01-02",
                positions={"A": 0.0},
                cash=1.0,
                equity=1.0,
                cost=0.0,
                net_return=0.0,
            )
        ],
    )
    value = explain_self_financing(prices, account, account)
    assert value["price_pnl"] == value["modeled_costs"] == value["net_return"] == 0


@pytest.mark.parametrize(
    "field, bad",
    [("equity", 2.0), ("cost", float("nan")), ("cash", -1), ("net_return", True)],
)
def test_invalid_or_unreconciled_cash_ledger_fails(field, bad):
    prices = dict(dates=["2024-01-01", "2024-01-02"], close={"A": [100, 110]})
    gross = cash_account(prices)
    net = copy.deepcopy(gross)
    net["periods"][0][field] = bad
    with pytest.raises(ValueError):
        explain_self_financing(prices, net, gross)


@pytest.mark.parametrize(
    "field, bad", [("accounting_model", "maker"), ("quote_currency", "USD")]
)
def test_counterfactual_cannot_mix_models_or_currencies(field, bad):
    prices = dict(dates=["2024-01-01", "2024-01-02"], close={"A": [100, 110]})
    net = cash_account(prices)
    gross = copy.deepcopy(net)
    gross[field] = bad
    with pytest.raises(ValueError):
        explain_self_financing(prices, net, gross)


def fractional_fixture():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    portfolio = [
        dict(date=d, equity=e, daily_return=r)
        for d, e, r in zip(dates, [100, 109, 98.1], [0.0, 0.09, -0.1])
    ]
    gross = [
        dict(date=d, equity=e, daily_return=r)
        for d, e, r in zip(dates, [100, 110, 99], [0.0, 0.1, -0.1])
    ]
    positions = [
        dict(
            date=d,
            code="A",
            target_weight=w,
            asset_return=r,
            cost=c,
            strategy_return=w * r - c,
        )
        for d, w, r, c in zip(dates, [0, 1, 1], [0, 0.1, -0.1], [0, 0.01, 0])
    ]
    return portfolio, positions, gross


def test_fractional_proxy_uses_the_net_nav_at_each_period():
    value = explain_fractional(
        *fractional_fixture(), initial_equity=100, quote_currency="USD"
    )
    assert value["price_pnl"] == pytest.approx(-0.9)
    assert value["modeled_costs"] == pytest.approx(1.0)
    assert value["net_pnl"] == pytest.approx(-1.9)
    assert value["counterfactual_cost_drag_return"] == pytest.approx(0.009)
    assert value["instruments"][0]["return_contribution"] == pytest.approx(-0.009)


def test_fractional_proxy_rejects_duplicate_or_missing_rows_and_bad_nav():
    portfolio, positions, gross = fractional_fixture()
    for rows in (positions + positions[:1], positions[:-1]):
        with pytest.raises(ValueError):
            explain_fractional(
                portfolio, rows, gross, initial_equity=100, quote_currency="USD"
            )
    portfolio[1]["equity"] = 999
    with pytest.raises(ValueError):
        explain_fractional(
            portfolio, positions, gross, initial_equity=100, quote_currency="USD"
        )


def test_explanation_rejects_nonfinite_prices_and_unknown_currency():
    prices = dict(dates=["2024-01-01", "2024-01-02"], close={"A": [100, float("inf")]})
    with pytest.raises(ValueError):
        explain_self_financing(prices, {}, {})
    with pytest.raises(ValueError):
        explain_fractional(
            *fractional_fixture(), initial_equity=100, quote_currency="BTC"
        )
