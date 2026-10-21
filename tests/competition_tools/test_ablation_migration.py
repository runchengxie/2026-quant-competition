"""Migration matches scientific semantics, never historical job IDs."""

import copy
import pytest
from competition_tools.check_ablation_migration import compare_metric_records


def row():
    return dict(
        market="US",
        strategy="sma_cross",
        variant_id="weekly",
        fee_bps=20,
        fold={"start": "2026-01-01", "end": "2026-03-01"},
        manifest_sha256="a" * 64,
        metrics={"net_return": 0.1, "flat_days": 0, "sharpe": None},
    )


def test_migration_joins_semantics_not_old_ids():
    a = row()
    b = {**a, "job_id": "old"}
    a["job_id"] = "new"
    assert compare_metric_records([a], [b])["matched"] == 1
    b = copy.deepcopy(b)
    b["metrics"]["net_return"] += 1e-11
    assert compare_metric_records([a], [b])["matched"] == 1
    b["metrics"]["net_return"] += 1e-5
    with pytest.raises(ValueError):
        compare_metric_records([a], [b])


def test_missing_duplicate_and_null_integer_semantics_are_errors():
    a = row()
    for others in [
        [],
        [a, a],
        [{**a, "metrics": {**a["metrics"], "flat_days": False}}],
        [{**a, "metrics": {**a["metrics"], "sharpe": 0}}],
    ]:
        with pytest.raises(ValueError):
            compare_metric_records([a], others)
