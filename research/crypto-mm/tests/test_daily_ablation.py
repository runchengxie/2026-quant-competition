"""Causal crypto overlays keep fixed scientific parameters."""

from datetime import date, timedelta
import copy
import math
from statistics import stdev
import pytest
from crypto_mm.daily.ablation import build_targets, evaluate_ablation, hysteresis_states
from crypto_mm.daily.study import evaluate_study


def bars():
    return {
        "dates": [
            (date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(342)
        ],
        "close": {"BTCUSDT": [100 + i + 5 * math.sin(i) for i in range(342)]},
    }


def test_hysteresis_retains_band_state():
    assert hysteresis_states([100] * 199 + [110, 101.5, 95])[199:202] == [
        True,
        True,
        False,
    ]
    assert hysteresis_states([100] * 199) == [False] * 199


def test_volatility_uses_only_twenty_prior_returns():
    b = bars()
    target = build_targets(b, "trend_200d", "vol_target_40pct")["targets"][0]
    values = b["close"]["BTCUSDT"]
    vol = stdev([values[j] / values[j - 1] - 1 for j in range(232, 252)]) * math.sqrt(
        365
    )
    assert sum(target.values()) == pytest.approx(min(1, 0.4 / vol))
    other = copy.deepcopy(b)
    other["close"]["BTCUSDT"][270:] = [1] * 72
    assert (
        build_targets(b, "trend_200d", "vol_target_40pct")["targets"][:18]
        == build_targets(other, "trend_200d", "vol_target_40pct")["targets"][:18]
    )


def test_target_cash_is_not_marked_exposure_guarantee():
    b = bars()
    b["close"]["BTCUSDT"][252] *= 2
    targets = build_targets(b, "trend_200d", "fixed_exposure_60pct")["targets"]
    assert targets[0] == {"BTCUSDT": 0.6}
    result = evaluate_ablation(
        b, "trend_200d", "fixed_exposure_60pct", fee_bps=10, quote_currency="USDT"
    )
    assert result["net"]["periods"][0]["exposure"] > 0.6
    assert all(0 <= sum(t.values()) <= 1 + 1e-12 for t in targets)


@pytest.mark.parametrize(
    "variant", ["hysteresis_2pct", "vol_target_40pct", "fixed_exposure_60pct"]
)
def test_empty_basket_fees_and_nonfinite_prices(variant):
    b = bars()
    b["close"] = {"BTCUSDT": [100.0] * 342}
    assert all(t == {} for t in build_targets(b, "trend_200d", variant)["targets"])
    b = bars()
    assert (
        evaluate_ablation(b, "trend_200d", variant, fee_bps=100, quote_currency="USDT")[
            "metrics"
        ]["net_return"]
        <= evaluate_ablation(
            b, "trend_200d", variant, fee_bps=0, quote_currency="USDT"
        )["metrics"]["net_return"]
    )
    b["close"]["BTCUSDT"][250] = float("inf")
    with pytest.raises(ValueError):
        build_targets(b, "trend_200d", variant)


def test_baseline_calls_unchanged_evaluator():
    for s in ["equal_weight", "momentum_63d", "trend_200d"]:
        assert evaluate_ablation(
            bars(), s, "baseline", fee_bps=25, quote_currency="USDT"
        ) == evaluate_study(bars(), s, fee_bps=25, quote_currency="USDT")
