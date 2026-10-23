"""Turnover buffers must retain shares rather than rebalance stale weights."""

import copy

import pytest

from equity_lab.study.controls import build_control_targets, evaluate_control
from equity_lab.study.ablation import build_targets, evaluate_ablation
from test_ablation_policies import bars


@pytest.mark.parametrize("fee", [20, 40])
@pytest.mark.parametrize(
    "arm,strategy,variant",
    [
        ("ew_daily", "equal_weight", "baseline"),
        ("ew_monthly", "equal_weight", "monthly"),
        ("mom20_daily", "momentum_20d", "baseline"),
        ("mom20_monthly", "momentum_20d", "monthly"),
    ],
)
def test_unbuffered_controls_preserve_legacy_periods(fee, arm, strategy, variant):
    old = evaluate_ablation(
        bars(), strategy, variant, fee_bps=fee, quote_currency="USD"
    )
    new = evaluate_control(bars(), arm, fee_bps=fee, quote_currency="USD")
    assert {k: new[k] for k in ("net", "gross", "metrics")} == old


def price_jump(jump):
    value = bars()
    value["close"] = {p: [100.0] * len(value["dates"]) for p in ("A", "B")}
    schedule = build_targets(value, "equal_weight", "monthly")["decision_flags"]
    offset = next(i for i, flag in enumerate(schedule) if i and flag)
    decision = 251 + offset
    value["close"]["A"][decision:] = [jump] * (len(value["dates"]) - decision)
    return value, offset


def test_skipped_rebalance_has_zero_turnover_and_real_drift():
    value, offset = price_jump(110)
    generated = build_control_targets(value, "ew_monthly_buffer20")
    result = evaluate_control(
        value, "ew_monthly_buffer20", fee_bps=40, quote_currency="USD"
    )
    assert generated["decision_flags"][0] is True
    assert generated["decision_flags"][offset] is False
    assert generated["targets"][offset]["A"] == pytest.approx(110 / 210)
    assert generated["diagnostics"]["skipped_scheduled_decisions"] >= 1
    for flag, period in zip(
        generated["decision_flags"], result["net"]["periods"], strict=True
    ):
        if not flag:
            assert period["turnover"] == period["cost"] == 0
        assert period["cash"] >= 0


def test_buffer_equality_trades_and_below_threshold_holds():
    value, offset = price_jump(150)
    assert build_control_targets(value, "ew_monthly_buffer20")["decision_flags"][offset]
    value, offset = price_jump(149.9)
    assert not build_control_targets(value, "ew_monthly_buffer20")["decision_flags"][
        offset
    ]


def test_empty_signal_exits_only_at_the_scheduled_checkpoint():
    value = bars()
    # Enter on an initially positive trend, then lose the signal mid-month.
    value["close"] = {"A": [100.0 + i for i in range(len(value["dates"]))]}
    schedule = build_targets(value, "momentum_20d", "monthly")["decision_flags"]
    next_month = next(i for i, flag in enumerate(schedule) if i > 1 and flag)
    value["close"]["A"][253:] = [50.0] * (len(value["dates"]) - 253)
    generated = build_control_targets(value, "mom20_monthly_buffer20")
    assert generated["targets"][0] == {"A": 1}
    assert generated["targets"][2] == {"A": 1}
    assert not generated["decision_flags"][2]
    assert generated["targets"][next_month] == {}
    assert generated["decision_flags"][next_month]


def test_future_changes_cannot_change_prior_targets():
    value = bars()
    other = copy.deepcopy(value)
    other["close"]["A"][290:] = [1.0] * 40
    for arm in ("ew_monthly_buffer20", "mom20_monthly_buffer20"):
        assert (
            build_control_targets(value, arm)["targets"][:38]
            == build_control_targets(other, arm)["targets"][:38]
        )


def test_controls_reject_invalid_arm_prices_and_currency():
    for arm in ("unknown", "ew_monthly_buffer20"):
        bad = bars()
        bad["close"]["A"][0] = float("nan")
        with pytest.raises(ValueError):
            build_control_targets(bad, arm)
    with pytest.raises(ValueError):
        evaluate_control(bars(), "ew_monthly", fee_bps=20, quote_currency="USDT")
