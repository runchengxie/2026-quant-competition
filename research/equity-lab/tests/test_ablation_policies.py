"""Calendar policies preserve actual holdings between decisions."""

from datetime import date, timedelta
import copy
import pytest
from equity_lab.study.ablation import build_targets, evaluate_ablation
from equity_lab.study.run import evaluate_study


def bars():
    return {
        "dates": [
            (date(2023, 4, 25) + timedelta(days=i)).isoformat() for i in range(330)
        ],
        "close": {
            "A": [100 + i for i in range(330)],
            "B": [200 - i * 0.1 for i in range(330)],
        },
    }


@pytest.mark.parametrize("variant", ["weekly", "monthly"])
def test_initial_entry_and_calendar_boundaries(variant):
    b = bars()
    out = build_targets(b, "equal_weight", variant)
    assert out["decision_flags"][0] is True
    for n, flag in enumerate(out["decision_flags"][1:], 253):
        now = date.fromisoformat(b["dates"][n - 1])
        prior = date.fromisoformat(b["dates"][n - 2])
        expected = (
            now.isocalendar()[:2] != prior.isocalendar()[:2]
            if variant == "weekly"
            else (now.year, now.month) != (prior.year, prior.month)
        )
        assert flag == expected


@pytest.mark.parametrize("variant", ["weekly", "monthly"])
def test_skipped_decisions_hold_quantities_without_cost(variant):
    b = bars()
    out = build_targets(b, "equal_weight", variant)
    result = evaluate_ablation(
        b, "equal_weight", variant, fee_bps=40, quote_currency="USD"
    )
    assert any(not f for f in out["decision_flags"])
    for flag, p in zip(out["decision_flags"], result["net"]["periods"]):
        if not flag:
            assert p["turnover"] == 0 and p["cost"] == 0


def test_future_prices_do_not_change_prior_targets():
    b = bars()
    other = copy.deepcopy(b)
    other["close"]["A"][290:] = [1] * 40
    assert (
        build_targets(b, "sma_cross", "weekly")["targets"][:38]
        == build_targets(other, "sma_cross", "weekly")["targets"][:38]
    )
    for strategy in [
        "buy_hold",
        "equal_weight",
        "momentum_20d",
        "sma_cross",
        "benchmark_buy_hold",
    ]:
        assert evaluate_ablation(
            b, strategy, "baseline", fee_bps=20, quote_currency="USD"
        ) == evaluate_study(b, strategy, fee_bps=20, quote_currency="USD")


def test_all_cash_and_invalid_schedule():
    b = bars()
    b["close"] = {"A": [400 - i for i in range(330)]}
    assert all(t == {} for t in build_targets(b, "momentum_20d", "monthly")["targets"])
    with pytest.raises(ValueError):
        build_targets(b, "buy_hold", "weekly")
