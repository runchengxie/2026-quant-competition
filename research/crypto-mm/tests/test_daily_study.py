"""Daily crypto studies preserve causal signals and buy-and-hold semantics."""

from datetime import date, timedelta
import pytest
from crypto_mm.daily.study import evaluate_study


def bars():
    return {
        "dates": [
            (date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(342)
        ],
        "close": {"BTCUSDT": [100.0] * 342, "ETHUSDT": [100.0] * 342},
    }


def test_crypto_equal_weight_is_buy_and_hold():
    data = bars()
    for i in range(252, 342):
        data["close"]["BTCUSDT"][i] = 200.0
    result = evaluate_study(data, "equal_weight", fee_bps=0, quote_currency="USDT")
    assert result["metrics"]["periods"] == 90
    assert result["metrics"]["net_return"] == pytest.approx(0.5)
    assert result["metrics"]["turnover"] == pytest.approx(1)
    assert result["net"]["periods"][-1]["weights"]["BTCUSDT"] == pytest.approx(2 / 3)


@pytest.mark.parametrize("strategy", ["equal_weight", "momentum_63d", "trend_200d"])
def test_future_crypto_prices_leave_prefix_unchanged(strategy):
    original, changed = bars(), bars()
    for i in range(280, 342):
        changed["close"]["BTCUSDT"][i] = 300.0
    before = evaluate_study(original, strategy, fee_bps=10, quote_currency="USDT")
    after = evaluate_study(changed, strategy, fee_bps=10, quote_currency="USDT")
    assert before["net"]["periods"][:28] == after["net"]["periods"][:28]


def test_crypto_trend_filter_enters_after_previous_close_cross():
    data = bars()
    for i in range(252, 342):
        data["close"]["BTCUSDT"][i] = 200.0
    result = evaluate_study(data, "trend_200d", fee_bps=0, quote_currency="USDT")
    assert result["net"]["periods"][0]["exposure"] == 0
    assert result["net"]["periods"][1]["exposure"] == 1
    assert result["metrics"]["net_return"] == 0


@pytest.mark.parametrize("price", [0, float("nan"), float("inf")])
def test_invalid_warmup_price_is_rejected_before_crypto_allocation(price):
    data = bars()
    data["close"]["BTCUSDT"][251] = price
    with pytest.raises(ValueError):
        evaluate_study(data, "equal_weight", fee_bps=10, quote_currency="USDT")
