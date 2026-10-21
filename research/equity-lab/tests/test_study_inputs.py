"""The leaf independently checks frozen file and source identities."""

import json
import pytest
from equity_lab.study.inputs import run_job
from study_fixtures import create_job


def test_job_writes_verified_summary_and_private_period_artifact(tmp_path):
    path, job = create_job(tmp_path / "fixture")
    result = run_job(path, tmp_path / "output")
    assert result["schema"] == "competition.daily_study_result.v1"
    assert result["job_id"] == job["job_id"]
    assert result["code_sha256"] == job["expected_leaf_sha256"]
    assert result["metrics"]["net_return"] == pytest.approx(1 / 1.002 - 1)
    assert result["methods"]["rebalance"] == "daily_target_weights"
    assert result["accepted_research"] is False
    assert json.loads((tmp_path / "output/result.json").read_text()) == result
    assert (tmp_path / "output/periods.json").is_file()
    with pytest.raises(FileExistsError):
        run_job(path, tmp_path / "output")


def test_changed_consumed_bytes_block_before_output(tmp_path):
    path, _ = create_job(tmp_path / "fixture")
    (path.parent / "dataset/normalized/A.csv").write_text("tampered")
    with pytest.raises(ValueError, match="DATASET_HASH_MISMATCH"):
        run_job(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_changed_code_identity_blocks_without_mutating_source(tmp_path):
    path, job = create_job(tmp_path / "fixture")
    path.write_text(json.dumps(job | {"expected_leaf_sha256": "f" * 64}))
    with pytest.raises(ValueError, match="CODE_CHANGED"):
        run_job(path, tmp_path / "output")


def test_job_cannot_silently_shrink_the_frozen_pool(tmp_path):
    path, job = create_job(tmp_path / "fixture")
    path.write_text(json.dumps(job | {"products": ["A"]}))
    with pytest.raises(ValueError, match="INVALID_STUDY_PRODUCTS"):
        run_job(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
