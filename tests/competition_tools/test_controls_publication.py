"""Caller-authored approval metadata must not grant publication rights."""

import pytest

from competition_tools.evaluation.controls.publication import (
    permission_verified,
    validate_public_controls,
)


def test_authorized_release_is_exactly_reviewed_and_retains_full_denominator():
    import json
    from pathlib import Path
    from competition_tools.evaluation.controls.publication import (
        REVIEWED_PUBLIC_CONTROLS,
    )
    from competition_tools.evaluation.study_identity import canonical_hash

    path = (
        Path(__file__).resolve().parents[2] / "site/src/data/strategy-controls.v1.json"
    )
    value = validate_public_controls(json.loads(path.read_text(encoding="utf-8")))
    assert value["status"] == "measured"
    assert canonical_hash(value) in REVIEWED_PUBLIC_CONTROLS
    assert value["coverage"] == dict(
        requested_jobs=420, completed_jobs=420, blocked_jobs=0
    )
    assert len(value["results"]) == 420
    assert len(value["pairs"]) == 224
    assert sum(r["market"] == "US" for r in value["results"]) == 132
    assert sum(r["market"] == "crypto" for r in value["results"]) == 288


@pytest.mark.parametrize(
    "value",
    [
        True,
        {"approved": True},
        {"status": "verified", "conclusion": "permitted"},
        {"source_sha256": "a" * 64, "reviewed": True},
    ],
)
def test_untrusted_permission_assertions_do_not_create_trust(value):
    assert not permission_verified(value, plan_sha256="b" * 64, results_sha256="c" * 64)


def test_public_payload_rejects_private_or_invented_fields():
    with pytest.raises(ValueError):
        validate_public_controls(
            {
                "schema": "competition.public_strategy_controls.v1",
                "status": "measured",
                "private_path": "private",
            }
        )


def measured_fixture():
    from competition_tools.evaluation.controls.catalog import ARMS, arm_spec
    from competition_tools.evaluation.controls.publication import RESTRICTIONS

    metrics = {
        k: 0.0
        for k in "net_return gross_return cost_drag volatility max_drawdown turnover total_costs mean_daily_turnover mean_exposure".split()
    }
    metrics.update(periods=63, flat_days=63, sharpe=None)
    row = dict(
        job_id="d" * 64,
        market="US",
        arm_id="ew_daily",
        fee_bps=20,
        quote_currency="USD",
        start="2024-01-02",
        end="2024-03-29",
        metrics=metrics,
    )
    return dict(
        schema="competition.public_strategy_controls.v1",
        status="measured",
        as_of="2026-10-23T00:00:00Z",
        code_commit="b" * 40,
        plan_sha256="c" * 64,
        coverage=dict(requested_jobs=1, completed_jobs=1, blocked_jobs=0),
        methods=[
            {"market": m, **arm_spec(m, a)} for m, arms in ARMS.items() for a in arms
        ],
        results=[row],
        pairs=[],
        blockers=[],
        restrictions=RESTRICTIONS,
    )


@pytest.mark.parametrize(
    "change", ["row_private", "metric_bool", "fee", "pair", "timestamp", "dupe"]
)
def test_public_measured_rows_are_strict_and_finite(change):
    value = measured_fixture()
    if change == "row_private":
        value["results"][0]["account"] = "private"
    elif change == "metric_bool":
        value["results"][0]["metrics"]["net_return"] = True
    elif change == "fee":
        value["results"][0]["fee_bps"] = 50
    elif change == "pair":
        value["pairs"] = [{"private": "not-a-pair"}]
    elif change == "timestamp":
        value["as_of"] = "not-a-time"
    else:
        value["results"] *= 2
        value["coverage"].update(requested_jobs=2, completed_jobs=2)
    with pytest.raises(ValueError):
        validate_public_controls(value)
