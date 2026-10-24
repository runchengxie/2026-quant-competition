"""Public cells preserve each requested fee, delay and unavailable result."""

import copy

import pytest

from competition_tools.evaluation.comparison_publication import (
    validate_cells,
    validate_public_comparison,
)


def cells():
    return [
        dict(
            window="2026-07-27",
            end="2026-08-21",
            arm=arm,
            fee_bps=fee,
            delay=delay,
            status="blocked",
            requested_dates=20,
            valid_dates=0,
            metrics=None,
        )
        for arm in ("equal_weight", "reversal", "ridge", "elastic_net")
        for fee in (0, 20, 40)
        for delay in (0, 1)
    ]


def test_fixed_grid_retains_unavailable_cells_without_zero_metrics():
    rows = cells()
    assert validate_cells("equity", rows, {"2026-07-27": "2026-08-21"}) == rows
    assert len(rows) == 24 and all(row["metrics"] is None for row in rows)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "boolean_fee", "fake_zero", "coverage", "private_path"],
)
def test_invalid_or_private_public_cells_fail(mutation):
    rows = cells()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "boolean_fee":
        rows[0]["fee_bps"] = False
    elif mutation == "fake_zero":
        rows[0]["metrics"] = {"net_return": 0}
    elif mutation == "coverage":
        rows[0]["valid_dates"] = 21
    elif mutation == "private_path":
        rows[0]["path"] = "C:/private/input.json"
    with pytest.raises(ValueError):
        validate_cells("equity", rows, {"2026-07-27": "2026-08-21"})


def test_unreviewed_public_artifact_is_never_accepted():
    with pytest.raises(ValueError):
        validate_public_comparison(
            {"schema": "competition.strategy_comparison_public.v1"}
        )
