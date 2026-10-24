"""Delayed decisions retain cash and real quantities instead of shifting returns."""

from datetime import date, timedelta

import pytest

from crypto_mm.daily.comparison import evaluate_comparison, comparison_targets
from crypto_mm.daily.weekly import evaluate_weekly


def bars():
    return dict(
        dates=[(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(342)],
        close={
            "A": [100 + i * 0.5 for i in range(342)],
            "B": [200 + i * 0.1 for i in range(342)],
        },
    )


def test_zero_delay_weekly_trend_exactly_matches_existing_account():
    source = bars()
    result = evaluate_comparison(source, "trend_weekly", 35, 0)
    original = evaluate_weekly(source, 35)["weekly_trend"]
    assert result["net"] == original["net"]
    assert result["gross"] == original["gross"]
    assert result["metrics"] == original["metrics"]


def test_buy_hold_only_trades_once_and_preserves_marked_units():
    result = evaluate_comparison(bars(), "buy_hold_equal_weight", 50, 0)
    periods = result["net"]["periods"]
    assert periods[0]["turnover"] > 0
    assert all(p["turnover"] == 0 for p in periods[1:])
    assert periods[-1]["weights"]["A"] != pytest.approx(0.5)


def test_delayed_initial_decision_stays_in_cash_then_recalculates_trade():
    result = evaluate_comparison(bars(), "buy_hold_equal_weight", 50, 1)
    first, second = result["net"]["periods"][:2]
    assert first["equity"] == 1 and first["cash"] == 1
    assert first["turnover"] == 0
    assert second["turnover"] > 0
    assert sum(second["positions"].values()) <= second["equity"]


def test_delay_shifts_targets_and_calendar_not_future_returns():
    weights, flags = comparison_targets(bars(), "fixed60_weekly", 0)
    delayed, later = comparison_targets(bars(), "fixed60_weekly", 1)
    assert later == [False] + flags[:-1]
    assert delayed == [{}] + weights[:-1]
    assert sum(weights[0].values()) == pytest.approx(0.6)


def test_matched_weekly_controls_match_scheduled_target_exposure():
    trend, flags = comparison_targets(bars(), "trend_weekly", 0)
    matched, other = comparison_targets(bars(), "matched_weekly", 0)
    assert flags == other
    assert [sum(w.values()) for w in trend] == pytest.approx(
        [sum(w.values()) for w in matched]
    )


def test_higher_cost_replays_holdings_and_cash_instead_of_subtracting_flat_fee():
    zero = evaluate_comparison(bars(), "fixed60_weekly", 0, 0)
    charged = evaluate_comparison(bars(), "fixed60_weekly", 50, 0)
    assert charged["net"]["periods"] != zero["net"]["periods"]
    assert charged["gross"] == zero["gross"]
    assert charged["metrics"]["net_return"] < zero["metrics"]["net_return"]
    assert charged["metrics"]["cost_drag"] != pytest.approx(
        charged["metrics"]["total_costs"]
    )


@pytest.mark.parametrize(
    "arm,fee,delay",
    [
        ("unknown", 35, 0),
        ("trend_weekly", True, 0),
        ("trend_weekly", 20, 0),
        ("trend_weekly", 35, True),
    ],
)
def test_invalid_identity_stops_before_replay(arm, fee, delay):
    with pytest.raises(ValueError):
        evaluate_comparison(bars(), arm, fee, delay)
