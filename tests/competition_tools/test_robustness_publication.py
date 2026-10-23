"""A caller boolean cannot authorize arbitrary public research statistics."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("value", [True, {"approved": True}, {"decision": "permitted"}])
def test_untrusted_publication_assertions_are_rejected(value):
    from competition_tools.evaluation.robustness.publication import permission_verified

    assert not permission_verified(value, plan_sha256="a" * 64, results_sha256="b" * 64)


def test_public_export_retains_every_job_and_capacity_assumption():
    from competition_tools.evaluation.robustness.publication import (
        validate_public_robustness,
    )

    path = (
        Path(__file__).resolve().parents[2]
        / "site/src/data/strategy-robustness.v1.json"
    )
    value = validate_public_robustness(json.loads(path.read_text()))
    assert value["status"] == "measured"
    assert value["coverage"] == dict(
        requested_jobs=114,
        completed_jobs=114,
        blocked_jobs=0,
        requested_capacity_checks=288,
        completed_capacity_checks=288,
    )
    assert sum(r["market"] == "US" for r in value["results"]) == 66
    assert sum(r["market"] == "crypto" for r in value["results"]) == 48
    assert len(value["us_pairs"]) == 66
    assert len(value["crypto_pairs"]) == 24
    assert len(value["capacity"]) == 288


def test_invented_public_payload_is_rejected():
    from competition_tools.evaluation.robustness.publication import (
        validate_public_robustness,
    )

    with pytest.raises(ValueError):
        validate_public_robustness(
            dict(
                schema="competition.public_strategy_robustness.v1",
                status="measured",
                private_path="private",
            )
        )


def test_readiness_cannot_leak_a_path_as_source_identity():
    from competition_tools.evaluation.robustness.publication import (
        validate_public_robustness,
    )

    path = (
        Path(__file__).resolve().parents[2]
        / "site/src/data/strategy-robustness.v1.json"
    )
    value = json.loads(path.read_text())
    value.update(
        status="readiness_only",
        results=[],
        us_pairs=[],
        crypto_pairs=[],
        capacity=[],
        code_commit="C:/private/source",
    )
    with pytest.raises(ValueError):
        validate_public_robustness(value)
