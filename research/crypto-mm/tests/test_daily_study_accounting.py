"""Economic contracts for the optional cash-funded study method."""

import pytest
from crypto_mm.daily.study_accounting import account_periods, summarize


def test_entry_fee_is_cash_funded():
    prices = {"dates": ["2024-01-01", "2024-01-02"], "close": {"A": [100.0, 100.0]}}
    result = account_periods(prices, [{"A": 1}], fee_bps=100, quote_currency="USD")
    period = result["periods"][0]
    assert period["equity"] == pytest.approx(1 / 1.01)
    assert period["cash"] >= 0
    assert period["cost"] == pytest.approx(0.01 / 1.01)
    assert period["equity"] == pytest.approx(
        period["cash"] + sum(period["positions"].values())
    )


def test_constant_targets_rebalance_drifted_holdings():
    prices = {
        "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "close": {"A": [100.0, 200.0, 200.0], "B": [100.0, 100.0, 100.0]},
    }
    result = account_periods(
        prices, [{"A": 0.5, "B": 0.5}] * 2, fee_bps=0, quote_currency="USD"
    )
    assert result["periods"][0]["equity"] == pytest.approx(1.5)
    assert result["periods"][1]["turnover"] == pytest.approx(1 / 3)
    assert result["periods"][1]["positions"] == pytest.approx({"A": 0.75, "B": 0.75})


def test_frictionless_buy_hold_and_no_terminal_sale():
    prices = {
        "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "close": {"A": [100.0, 200.0, 300.0], "B": [100.0, 100.0, 100.0]},
    }
    result = account_periods(
        prices,
        [{"A": 0.5, "B": 0.5}, {"A": 2 / 3, "B": 1 / 3}],
        fee_bps=0,
        quote_currency="HKD",
    )
    assert result["periods"][-1]["equity"] == pytest.approx(2)
    assert result["periods"][-1]["turnover"] == pytest.approx(0, abs=1e-12)
    assert result["periods"][-1]["positions"]["A"] == pytest.approx(1.5)


def test_actual_liquidation_charged_once_then_cash_is_flat():
    prices = {
        "dates": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "close": {"A": [100.0] * 4},
    }
    net = account_periods(
        prices, [{"A": 1}, {}, {}], fee_bps=100, quote_currency="USDT"
    )
    gross = account_periods(
        prices, [{"A": 1}, {}, {}], fee_bps=0, quote_currency="USDT"
    )
    assert net["periods"][1]["cost"] == pytest.approx(0.01 / 1.01)
    assert net["periods"][2]["cost"] == 0
    metrics = summarize(net, gross, periods_per_year=365)
    assert metrics["flat_days"] == 1
    assert metrics["mean_daily_turnover"] == pytest.approx(metrics["turnover"] / 3)
    assert metrics["cost_drag"] > 0


def test_all_cash_has_null_sharpe_and_zero_drawdown():
    prices = {
        "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "close": {"A": [100.0, 200.0, 50.0]},
    }
    result = account_periods(prices, [{}, {}], fee_bps=20, quote_currency="USD")
    metrics = summarize(result, result, periods_per_year=252)
    assert metrics["sharpe"] is None
    assert metrics["net_return"] == 0
    assert metrics["max_drawdown"] == 0
    assert metrics["flat_days"] == 2


@pytest.mark.parametrize(
    "target", [{"A": float("nan")}, {"A": -1}, {"A": 1.1}, {"UNKNOWN": 1}, {"A": True}]
)
def test_invalid_weights_never_create_undeclared_leverage(target):
    with pytest.raises(ValueError):
        account_periods(
            {"dates": ["2024-01-01", "2024-01-02"], "close": {"A": [100.0, 100.0]}},
            [target],
            fee_bps=0,
            quote_currency="USD",
        )


@pytest.mark.parametrize("price", [float("nan"), float("inf"), 0, -1, True])
def test_invalid_prices_are_rejected(price):
    with pytest.raises(ValueError):
        account_periods(
            {"dates": ["2024-01-01", "2024-01-02"], "close": {"A": [100.0, price]}},
            [{}],
            fee_bps=0,
            quote_currency="USD",
        )
