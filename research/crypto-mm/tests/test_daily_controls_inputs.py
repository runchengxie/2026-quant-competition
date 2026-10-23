"""The standalone controls producer checks policy, bytes and source identity."""

import json
from pathlib import Path

import pytest

from study_fixtures import create_job, canonical_hash
from crypto_mm.daily.study_inputs import _source_hash
from crypto_mm.daily.controls_inputs import (
    run_controls_job,
    policy_spec,
    CATALOG_SHA256,
)


def create_control(root, arm="ew_fixed60"):
    path, old = create_job(root, crypto=True)
    job = {
        k: old[k]
        for k in "market project products benchmark quote_currency dates fold manifest manifest_sha256 input_files input_slice expected_leaf_sha256 fee_bps accounting_model execution_assumption accepted_research code_commit plan_sha256".split()
    }
    policy = policy_spec(arm)
    job.update(
        schema="competition.strategy_controls_job.v1",
        arm_id=arm,
        parameters=policy["parameters"],
        evidence_role=policy["role"],
        catalog_sha256=CATALOG_SHA256,
    )
    job["expected_leaf_sha256"] = _source_hash()
    job["job_id"] = canonical_hash(
        {k: v for k, v in job.items() if k not in {"job_id", "plan_sha256"}}
    )
    path.write_text(json.dumps(job))
    return path, job


def test_control_job_writes_finite_bound_periods(tmp_path):
    path, job = create_control(tmp_path / "input")
    result = run_controls_job(path, tmp_path / "output")
    assert result["status"] == "completed"
    assert result["schema"] == "competition.strategy_controls_result.v1"
    assert result["job_id"] == job["job_id"]
    periods = json.loads((tmp_path / "output/periods.json").read_text())
    assert periods["plan_sha256"] == job["plan_sha256"]
    assert len(periods["net"]) == 90
    assert result["metrics"]["net_return"] == pytest.approx(1 / 1.0006 - 1)
    with pytest.raises(FileExistsError):
        run_controls_job(path, tmp_path / "output")


@pytest.mark.parametrize("change", ["policy", "code", "input", "extra"])
def test_changed_controls_contract_blocks_without_output(tmp_path, change):
    path, job = create_control(tmp_path / "input")
    if change == "policy":
        job["parameters"]["multiplier"] = 0.1
    elif change == "code":
        job["expected_leaf_sha256"] = "0" * 64
    elif change == "extra":
        job["private_override"] = True
    else:
        (Path(job["manifest"]).parent / "normalized/BTCUSDT.csv").write_text("changed")
    job["job_id"] = canonical_hash(
        {k: v for k, v in job.items() if k not in {"job_id", "plan_sha256"}}
    )
    path.write_text(json.dumps(job))
    with pytest.raises(ValueError):
        run_controls_job(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
