import math

import pytest

from equity_lab.evaluation.posthoc_diagnostics import daily_diagnostic, forward_label
from equity_lab.evaluation.posthoc_statistics import bootstrap_means, holm, uncertainty


def test_quintiles_use_scores_before_label_mask_and_keep_ties():
    row = daily_diagnostic(list(range(10)), [None] * 8 + [0.2, 0.4])
    assert row["edges"] == pytest.approx([1.8, 3.6, 5.4, 7.2])
    assert row["quintile_counts"] == [0, 0, 0, 0, 2]
    assert row["quintile_returns"] == [None, None, None, None, pytest.approx(0.3)]
    assert row["coverage"] == 0.2
    assert row["rank_ic"] is None
    ties = daily_diagnostic([0] * 16 + [1, 2, 3, 4], [0.0] * 20)
    assert ties["quintile_reason"] == "duplicate_quantile_edges"
    assert ties["edges"] is None


def test_shapes_nonfinite_and_constant():
    with pytest.raises(ValueError):
        daily_diagnostic([1], [])
    row = daily_diagnostic([None, math.nan, math.inf, 1], [1, 1, 1, 0.2])
    assert row["finite_scores"] == 1
    assert row["quintile_reason"] == "fewer_than_five_distinct_scores"


def test_strict_label_identity_action_price_and_tail():
    calendar = [
        "2026-01-01",
        "2026-01-02",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08",
    ]
    rows = {
        d: dict(open=10, close=11, valid=True, action_boundary=False, ticker="X")
        for d in calendar
    }
    assert forward_label(calendar, rows, calendar[0], 5) == pytest.approx(0.1)
    rows[calendar[2]]["ticker"] = "Y"
    assert forward_label(calendar, rows, calendar[0], 5) is None
    rows[calendar[2]]["ticker"] = "X"
    rows[calendar[1]]["action_boundary"] = True
    assert forward_label(calendar, rows, calendar[0], 5) is None
    assert forward_label(calendar, rows, calendar[-1], 1) is None


def test_hac_hand_reference_fixed_bootstrap_and_full_holm():
    # Alternating +/-1: lag0 population variance=1; corrected mean variance=1/39.
    values = [-1.0, 1.0] * 20
    grid = [f"{i:03}" for i in range(40)]
    got = uncertainty(values, 1, grid, grid)
    assert got["se"] == pytest.approx(math.sqrt(1 / 39))
    assert got["p"] == 1
    assert got["ci95"] == pytest.approx(
        [-1.959963984540054 / math.sqrt(39), 1.959963984540054 / math.sqrt(39)]
    )
    assert uncertainty(values, 1, grid, grid) == got
    assert bootstrap_means([1, 2, 3, 4], 2, [[0, 2], [1, 1]]) == [2.5, 2.5]
    assert bootstrap_means([1, 2, 3, 4], 2, [[0, 0], [2, 2]]) == [1.5, 3.5]
    assert holm([0.01, 0.02, None, 0.04]) == [0.04, 0.06, None, 0.08]
    assert uncertainty(values, 20, grid, grid)["reason"] == "insufficient_sessions"
    assert uncertainty(values[:-1], 1, grid[:-1], grid)["status"] == "available"
    assert (
        uncertainty(values, 1, grid, grid[:20] + ["gap"] + grid[20:])["reason"]
        == "noncontiguous_calendar"
    )
    assert (
        uncertainty(values[:-1] + [None], 1, grid, grid)["reason"]
        == "missing_or_nonfinite_daily_ic"
    )
    assert uncertainty([0.1] * 40, 1, grid, grid)["reason"] == "constant_daily_ic"


def test_hac_lag_four_reference():
    values = [float(i % 7 - 3) / 3 for i in range(40)]
    grid = list(range(40))
    mean = sum(values) / 40
    z = [v - mean for v in values]
    numerator = sum(v * v for v in z)
    for lag in range(1, 5):
        numerator += 2 * (1 - lag / 5) * sum(z[i] * z[i - lag] for i in range(lag, 40))
    expected = math.sqrt(numerator / (40 * 39))
    got = uncertainty(values, 5, grid, grid)
    assert got["se"] == pytest.approx(expected)
    assert got["p"] == pytest.approx(math.erfc(abs(mean) / expected / math.sqrt(2)))


def test_missing_prediction_does_not_get_silently_dropped_from_daily_ic():
    row = daily_diagnostic([None] + list(range(30)), list(range(31)))
    assert row["rank_ic"] is None
    assert row["ic_reason"] == "missing_predictions"


def test_decision_day_ohlc_and_completed_action_do_not_change_future_pricing_interval():
    calendar = ["2026-01-01", "2026-01-02"]
    rows = {
        calendar[0]: dict(
            open=None, close=None, valid=False, action_boundary=True, ticker="OLD"
        ),
        calendar[1]: dict(
            open=10, close=11, valid=True, action_boundary=False, ticker="NEW"
        ),
    }
    assert forward_label(calendar, rows, calendar[0], 1) == pytest.approx(0.1)
