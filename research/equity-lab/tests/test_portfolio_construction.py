"""Portfolio policies remain usable without importing the replay engine."""

from types import SimpleNamespace

import pandas as pd
import pytest

from equity_lab.portfolio.construction import (
    apply_daily_turnover_limit,
    apply_static_weight_limits,
    build_raw_weights,
)


def limits(**overrides):
    return SimpleNamespace(
        **dict(max_positions=None, max_single_name_weight=None, max_gross_exposure=None)
        | overrides
    )


def test_scores_use_identifier_tie_break_and_preserve_cash_after_caps():
    frame = pd.DataFrame(
        {"date": ["2024-01-01"] * 3, "code": ["C", "B", "A"], "signal": [1, 1, 1]}
    )
    policy = limits(max_positions=2, max_single_name_weight=0.3, max_gross_exposure=0.5)
    raw = build_raw_weights(frame, policy)
    assert raw.tolist() == [0.0, 0.5, 0.5]
    actual = apply_static_weight_limits(raw, frame["date"], policy)
    assert actual.tolist() == [0.0, 0.25, 0.25]


def test_precomputed_weights_preserve_cash_and_take_priority_over_scores():
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 2,
            "code": ["A", "B"],
            "signal": [0, 0],
            "weight_score": [9, 1],
            "precomputed_weight": [0.2, 0.3],
        }
    )
    assert build_raw_weights(frame, limits()).tolist() == [0.2, 0.3]


@pytest.mark.parametrize(
    "budget, expected",
    [(0.0, [0, 0, 0, 0]), (0.3, [0.15, 0.15, 0.3, 0.3]), (None, [0.5] * 4)],
)
def test_turnover_budget_carries_previous_weights_across_dates(budget, expected):
    frame = pd.DataFrame(
        {"date": ["2024-01-01"] * 2 + ["2024-01-02"] * 2, "code": ["A", "B"] * 2}
    )
    actual = apply_daily_turnover_limit(frame, pd.Series([0.5] * 4), budget)
    assert actual.tolist() == pytest.approx(expected)


def test_empty_portfolio_does_not_invent_positions():
    frame = pd.DataFrame(
        {
            "date": pd.Series(dtype=str),
            "code": pd.Series(dtype=str),
            "signal": pd.Series(dtype=float),
        }
    )
    assert build_raw_weights(frame, limits()).empty
