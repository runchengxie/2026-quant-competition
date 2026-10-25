"""Saved crypto controls must be paired under identical replay dimensions."""

import pytest

from competition_tools.evaluation.paired_crypto import compare_pairs


def row(arm, fee=35):
    return dict(
        arm=arm,
        window="2024-01-01",
        end="2024-03-30",
        fee_bps=fee,
        delay=0,
        net_return=0.1,
        mean_post_trade_exposure=0.5,
    )


def test_pair_difference_keeps_exact_conditions_and_missing_outcomes():
    trend = row("trend_weekly") | {"net_return": 0.13}
    control = row("matched_weekly")
    result = compare_pairs([trend, control, row("trend_weekly", 50)])
    assert result["requested"] == 2 and result["comparable"] == 1
    assert result["rows"][0]["return_difference"] == pytest.approx(0.03)
    assert result["rows"][1]["status"] == "blocked"
    assert result["same_volatility_claimed"] is False


def test_duplicates_and_nonfinite_results_cannot_enter_pair_summary():
    with pytest.raises(ValueError):
        compare_pairs([row("trend_weekly"), row("trend_weekly")])
    with pytest.raises(ValueError):
        compare_pairs([row("trend_weekly") | {"net_return": float("nan")}])
