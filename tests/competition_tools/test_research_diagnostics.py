import math

import pytest

from competition_tools.evaluation.research_diagnostics import (
    cost_threshold,
    crypto_attribution,
)


def test_exact_round_trip_break_even_is_not_linear_cost_interpolation():
    result = cost_threshold([0.1, -0.02])
    fee = result["break_even_one_way_bps"] / 10000
    assert math.prod(1 + r for r in [0.1, -0.02]) * ((1 - fee) / (1 + fee)) ** 2 == pytest.approx(1)
    assert result["dates"] == 2
    assert cost_threshold([-0.1])["break_even_one_way_bps"] is None
    assert cost_threshold([0.0])["break_even_one_way_bps"] == 0


@pytest.mark.parametrize("values", [[], [True], [float("nan")], [-1], [float("inf")]])
def test_cost_threshold_rejects_invalid_returns(values):
    with pytest.raises(ValueError):
        cost_threshold(values)


def account(fee=0):
    funded = 1 / (1 + 0.5 * fee)
    return dict(accounting_model="self_financing_daily.v1", quote_currency="USDT", periods=[dict(
        date="2026-01-02", equity=1.05 * funded, cash=0.5 * funded,
        positions={"A": 0.55 * funded, "B": 0.0}, cost=0.5 * funded * fee,
        net_return=1.05 * funded - 1,
    )])


def test_attribution_separates_market_underinvestment_selection_and_fees():
    prices = dict(dates=["2026-01-01", "2026-01-02"], close={"A": [100, 110], "B": [100, 120]})
    result = crypto_attribution(prices, account(0.01))
    parts = result["components"]
    assert parts["market"] == pytest.approx(0.15)
    assert parts["exposure"] < 0
    assert parts["selection"] < 0
    assert parts["cost"] < 0
    assert sum(parts.values()) == pytest.approx(result["net_return"])
    assert result["dates"] == 1
    assert result["down_market_dates"] == 0
    assert result["causal"] is False


def test_cash_and_down_market_days_keep_zero_price_contribution():
    prices = dict(dates=["2026-01-01", "2026-01-02"], close={"A": [100, 90]})
    cash = dict(accounting_model="self_financing_daily.v1", quote_currency="USDT", periods=[dict(date="2026-01-02", equity=1.0, cash=1.0, positions={"A": 0.0}, cost=0.0, net_return=0.0)])
    result = crypto_attribution(prices, cash)
    assert result["components"] == pytest.approx(dict(market=-0.1, exposure=0.1, selection=0, cost=0))
    assert result["down_market_dates"] == 1
    assert result["mean_post_trade_exposure"] == 0


def test_attribution_rejects_changed_ledger_and_currency():
    prices = dict(dates=["2026-01-01", "2026-01-02"], close={"A": [100, 110], "B": [100, 120]})
    value = account()
    value["periods"][0]["cash"] += 0.1
    with pytest.raises(ValueError):
        crypto_attribution(prices, value)
    value = account()
    value["quote_currency"] = "USD"
    with pytest.raises(ValueError):
        crypto_attribution(prices, value)
