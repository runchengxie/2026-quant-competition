"""Policy matching and exposure matching are separate scientific controls."""

import copy
import math
from statistics import stdev

import pytest

from crypto_mm.daily.controls import build_control_targets, evaluate_control
from crypto_mm.daily.ablation import evaluate_ablation, build_targets
from test_daily_ablation import bars


@pytest.mark.parametrize("fee", [0, 10, 25])
@pytest.mark.parametrize(
    "arm,strategy,variant",
    [
        ("ew_legacy", "equal_weight", "baseline"),
        ("trend200_legacy", "trend_200d", "baseline"),
        ("trend200_vol40_legacy", "trend_200d", "vol_target_40pct"),
        ("trend200_fixed60_legacy", "trend_200d", "fixed_exposure_60pct"),
    ],
)
def test_legacy_controls_are_exact_replays(fee, arm, strategy, variant):
    old = evaluate_ablation(
        bars(), strategy, variant, fee_bps=fee, quote_currency="USDT"
    )
    new = evaluate_control(bars(), arm, fee_bps=fee, quote_currency="USDT")
    assert {k: new[k] for k in ("net", "gross", "metrics")} == old


def test_strict_zero_volatility_stays_cash_and_preserves_legacy_fallback():
    value = bars()
    value["close"]["BTCUSDT"] = [float(2**i) for i in range(342)]
    for arm in ("trend200_vol40_strict", "ew_vol40_strict", "ew_trend_gross_matched"):
        generated = build_control_targets(value, arm)
        assert all(sum(t.values()) == 0 for t in generated["targets"])
        assert generated["diagnostics"]["zero_volatility_decisions"] == 90
    assert all(
        t == {"BTCUSDT": 1.0}
        for t in build_targets(value, "trend_200d", "vol_target_40pct")["targets"]
    )


def test_twenty_completed_returns_and_sample_stdev_determine_scale():
    value = bars()
    prices = value["close"]["BTCUSDT"]
    volatility = stdev(
        [prices[j] / prices[j - 1] - 1 for j in range(232, 252)]
    ) * math.sqrt(365)
    for arm in ("trend200_vol40_strict", "ew_vol40_strict"):
        generated = build_control_targets(value, arm)
        assert sum(generated["targets"][0].values()) == pytest.approx(
            min(1.0, 0.4 / volatility)
        )
    previous = copy.deepcopy(value)
    previous["close"]["BTCUSDT"][230] *= 10
    assert (
        build_control_targets(value, "ew_vol40_strict")["targets"][0]
        == build_control_targets(previous, "ew_vol40_strict")["targets"][0]
    )


def test_same_gross_control_tracks_known_exposure_not_future_returns():
    value = bars()
    value["close"]["ETHUSDT"] = [400 - i * 0.5 for i in range(342)]
    trend = build_control_targets(value, "trend200_vol40_strict")
    matched = build_control_targets(value, "ew_trend_gross_matched")
    for target, control in zip(trend["targets"], matched["targets"], strict=True):
        assert sum(target.values()) == pytest.approx(sum(control.values()), abs=1e-12)
        assert control.get("ETHUSDT", 0) == control.get("BTCUSDT", 0)
    other = copy.deepcopy(value)
    other["close"]["BTCUSDT"][270:] = [1] * 72
    assert (
        matched["targets"][:18]
        == build_control_targets(other, "ew_trend_gross_matched")["targets"][:18]
    )
    assert matched["diagnostics"]["exposure_source_arm"] == "trend200_vol40_strict"


def test_empty_trend_and_fixed_exposure_controls_have_explicit_cash():
    value = bars()
    value["close"] = {"BTCUSDT": [400 - i for i in range(342)]}
    assert all(
        t == {}
        for t in build_control_targets(value, "trend200_vol40_strict")["targets"]
    )
    assert all(
        sum(t.values()) == pytest.approx(0.6)
        for t in build_control_targets(value, "ew_fixed60")["targets"]
    )
    result = evaluate_control(value, "ew_fixed60", fee_bps=25, quote_currency="USDT")
    assert all(p["cash"] >= 0 for p in result["net"]["periods"])


@pytest.mark.parametrize("bad", ["short", "nonfinite", "overflow"])
def test_strict_controls_reject_bad_history_or_derived_returns(bad):
    value = bars()
    if bad == "short":
        value["dates"] = value["dates"][:252]
        value["close"]["BTCUSDT"] = value["close"]["BTCUSDT"][:252]
    elif bad == "nonfinite":
        value["close"]["BTCUSDT"][240] = float("nan")
    else:
        value["close"]["BTCUSDT"][232] = 1e-200
        value["close"]["BTCUSDT"][233] = 1e200
        value["close"]["BTCUSDT"][251] = 1e201
    with pytest.raises(ValueError):
        build_control_targets(value, "trend200_vol40_strict")
