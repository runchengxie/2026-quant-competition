"""Independent producer checks v2 identity while preserving v1 CLI."""

import json
import subprocess
import sys
import pytest
from study_fixtures import create_job
from crypto_mm.daily.ablation_inputs import run_ablation_job, policy_spec, job_hash
from crypto_mm.daily.study_inputs import _source_hash


def create_ablation(root):
    p, j = create_job(root, crypto=True)
    j["strategy"] = "trend_200d"
    j["parameters"] = {"long_window": 200}
    j.update(
        schema="competition.daily_study_job.v2",
        **policy_spec(j["strategy"], "fixed_exposure_60pct"),
        catalog_sha256="a" * 64,
        origin={
            **{
                k: "b" * 64
                for k in [
                    "probe_protocol_sha256",
                    "diagnostic_protocol_sha256",
                    "evidence_manifest_sha256",
                ]
            },
            "stage": "retrospective",
            "retrospective": True,
            "accepted_research": False,
        },
    )
    j["expected_leaf_sha256"] = _source_hash()
    j["job_id"] = job_hash(j)
    p.write_text(json.dumps(j))
    return p, j


def test_producer_binds_variant_and_private_periods(tmp_path):
    p, j = create_ablation(tmp_path / "fixture")
    result = run_ablation_job(p, tmp_path / "out")
    assert result["schema"] == "competition.daily_study_result.v2"
    assert result["variant_id"] == "fixed_exposure_60pct"
    assert (
        json.loads((tmp_path / "out/periods.json").read_text())["schema"]
        == "competition.daily_study_periods.v2"
    )
    assert (
        result["methods"]["method_id"]
        == "crypto.trend_200d.fixed_exposure_60pct.self_financing_daily.v1"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("variant_parameters", {"schedule": "daily"}),
        ("evidence_role", "forward_validated"),
        ("job_id", "a" * 64),
    ],
)
def test_post_hoc_role_cannot_be_overridden(tmp_path, key, value):
    p, j = create_ablation(tmp_path / "fixture")
    j[key] = value
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError):
        run_ablation_job(p, tmp_path / "out")


def test_v1_cli_contract_is_unchanged(tmp_path):
    p, j = create_job(tmp_path / "fixture", crypto=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.daily.study_cli",
            "--job",
            str(p),
            "--output-root",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        json.loads((tmp_path / "out/result.json").read_text())["schema"]
        == "competition.daily_study_result.v1"
    )
    assert (
        subprocess.run(
            [sys.executable, "-m", "crypto_mm.daily.study_cli", "--help"],
            capture_output=True,
        ).returncode
        == 0
    )
