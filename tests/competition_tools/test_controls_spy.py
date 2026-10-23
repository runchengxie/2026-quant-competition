"""Benchmark periods and entry fees match the frozen strategy windows."""

import pytest


def test_spy_uses_pre_scoring_close_and_entry_fee():
    from competition_tools.check_controls_spy import spy_comparison

    job = dict(
        dates=["warmup", "before", "first", "last"],
        fold=dict(warmup_periods=2, start="first", end="last"),
        fee_bps=20,
    )
    result = spy_comparison(
        job, {"warmup": 1, "before": 100, "first": 105, "last": 110}, 0.08
    )
    assert result["spy_gross_price_return"] == pytest.approx(0.1)
    assert result["spy_fee_matched_net_return"] == pytest.approx(1.1 / 1.002 - 1)
    assert result["excess_vs_spy_gross"] == pytest.approx(-0.02)
    assert result["excess_vs_spy_fee_matched_net"] == pytest.approx(
        0.08 - (1.1 / 1.002 - 1)
    )


def test_spy_rejects_missing_boundary_or_nonfinite_prices():
    from competition_tools.check_controls_spy import spy_comparison

    job = dict(
        dates=["before", "last"],
        fold=dict(warmup_periods=1, start="last", end="last"),
        fee_bps=40,
    )
    for prices in ({"last": 100}, {"before": 100, "last": float("nan")}):
        with pytest.raises(ValueError):
            spy_comparison(job, prices, 0.08)
