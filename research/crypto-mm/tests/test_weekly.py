from copy import deepcopy
from datetime import date, timedelta

import pytest

from crypto_mm.daily.study_accounting import account_periods


def test_hold_keeps_actual_units_cash_and_has_zero_trade():
    prices = {
        "dates": ["2026-08-03", "2026-08-04", "2026-08-05"],
        "close": {"A": [100, 200, 100], "B": [100, 100, 100]},
    }
    net = account_periods(
        prices,
        [{"A": 0.5, "B": 0.5}] * 2,
        fee_bps=50,
        quote_currency="USDT",
        decision_flags=[True, False],
    )
    assert net["periods"][1]["turnover"] == 0
    assert net["periods"][1]["cost"] == 0
    assert net["periods"][1]["positions"]["A"] == pytest.approx(
        net["periods"][0]["positions"]["A"] / 2
    )
    assert net["periods"][1]["cash"] == net["periods"][0]["cash"]
    assert net["periods"][1]["equity"] == pytest.approx(1 / 1.005)


def bars():
    dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(342)]
    return {
        "dates": dates,
        "close": {
            "A": [100 + i for i in range(342)],
            "B": [100 + i * 0.1 for i in range(342)],
        },
    }


def test_weekly_initial_and_monday_calendar():
    from crypto_mm.daily.weekly import weekly_flags

    assert weekly_flags(["2026-08-02", "2026-08-03", "2026-08-04", "2026-08-10"]) == [
        True,
        True,
        False,
        True,
    ]
    assert weekly_flags(["2026-08-03", "2026-08-04"]) == [True, False]


def test_weekly_control_matches_current_exposure_without_future_prices():
    from crypto_mm.daily.weekly import evaluate_weekly

    first = evaluate_weekly(bars(), 50)
    assert len(first) == 5
    trend = first["weekly_trend"]
    control = first["weekly_exposure_matched"]
    assert control["decision_exposure"] == pytest.approx(trend["decision_exposure"])
    changed = deepcopy(bars())
    changed["close"]["A"][-1] *= 10
    second = evaluate_weekly(changed, 50)
    assert (
        second["weekly_exposure_matched"]["decision_exposure"]
        == control["decision_exposure"]
    )
    for name in first:
        assert all(p["cash"] >= 0 for p in first[name]["net"]["periods"])


def test_default_accounting_remains_identical_to_all_true_flags():
    prices = {
        "dates": ["2026-08-03", "2026-08-04", "2026-08-05"],
        "close": {"A": [10, 20, 10]},
    }
    args = dict(fee_bps=35, quote_currency="USDT")
    assert account_periods(prices, [{"A": 1}] * 2, **args) == account_periods(
        prices, [{"A": 1}] * 2, **args, decision_flags=[True, True]
    )


def test_hold_flags_reject_truthy_non_booleans():
    prices = {"dates": ["2026-08-03", "2026-08-04"], "close": {"A": [10, 20]}}
    with pytest.raises(ValueError):
        account_periods(
            prices, [{"A": 1}], fee_bps=35, quote_currency="USDT", decision_flags=[1]
        )
