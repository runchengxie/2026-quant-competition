"""Hand-computed daily research contracts catch timing and accounting errors."""

import pytest

from crypto_mm.daily.evaluation import evaluate


def bars(prices):
    from datetime import date, timedelta

    dates = [
        (date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(len(prices))
    ]
    return {
        "dates": dates,
        "close": {"BTCUSDT": prices, "ETHUSDT": prices},
        "quote_currency": "USDT",
        "calendar": "365",
    }


def test_flat_buy_hold_charges_initial_allocation_once():
    value = evaluate(bars([100.0] * 70), "equal_weight", fee_bps=10)
    assert value["net_return"] == pytest.approx(-0.001)
    assert value["turnover"] == pytest.approx(1.0)
    assert value["quote_currency"] == "USDT"
    assert value["periods_per_year"] == 365


def test_momentum_waits_for_history_and_lags_signal():
    prices = [100.0] * 64 + [200.0, 400.0, 400.0]
    result = evaluate(bars(prices), "momentum_63d", fee_bps=0)
    assert result["periods"][0]["exposure"] == 0
    assert result["periods"][1]["exposure"] == 0
    assert result["periods"][2]["exposure"] == 1
    assert result["net_return"] == pytest.approx(1.0)


def test_future_price_cannot_change_previous_holdings():
    first = evaluate(bars([100 + i for i in range(80)]), "momentum_63d", fee_bps=10)
    second = evaluate(
        bars([100 + i for i in range(79)] + [1_000_000]), "momentum_63d", fee_bps=10
    )
    assert [p["weights"] for p in first["periods"]] == [
        p["weights"] for p in second["periods"]
    ]


@pytest.mark.parametrize("change", [{"quote_currency": "USD"}, {"calendar": "252"}])
def test_incompatible_daily_identity_rejected(change):
    with pytest.raises(ValueError):
        evaluate(bars([100.0] * 70) | change, "equal_weight", fee_bps=10)


def test_short_history_is_not_zero_performance_success():
    with pytest.raises(ValueError, match="INSUFFICIENT_HISTORY"):
        evaluate(bars([100.0] * 63), "momentum_63d", fee_bps=10)
