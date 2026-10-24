"""Experiment records bind actual bytes and never accept incomplete runs."""

import json
import shutil
import subprocess

import pytest

from competition_tools.evaluation.run_record import (
    init_run,
    freeze_run,
    finish_run,
    verify_run,
)


@pytest.fixture
def frozen(tmp_path):
    repo = tmp_path / "repo"
    for name in ("src", "research/equity-lab/src", "research/crypto-mm/src"):
        folder = repo / name
        folder.mkdir(parents=True)
        (folder / "module.py").write_text("VALUE = 1\n")
    for name in (".", "research/equity-lab", "research/crypto-mm"):
        (repo / name / "pyproject.toml").write_text("# synthetic metadata\n")
        (repo / name / "uv.lock").write_text("# synthetic lock\n")
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    run = init_run(tmp_path / "run")
    (run / "input.json").write_text('{"synthetic":true}\n')
    plan = freeze_run(repo, run, ["input.json"], {"fee_bps": 20, "synthetic": True})
    return repo, run, plan


def test_completed_record_binds_inputs_source_locks_parameters_and_artifacts(frozen):
    _, run, plan = frozen
    (run / "result.json").write_text('{"return":0.0}\n')
    result = finish_run(
        run, ["result.json"], status="completed", environments={"python": "3.12"}
    )
    checked = verify_run(run)
    assert checked == result
    assert result["plan_sha256"] == plan["plan_sha256"]
    assert len(plan["code"]["lock_sha256"]) == 3
    assert result["artifacts"][0]["sha256"]
    with pytest.raises(FileExistsError):
        finish_run(run, ["result.json"], status="completed", environments={})


@pytest.mark.parametrize(
    "name",
    [
        "input.json",
        "source/source/src/module.py",
        "source/source/uv.lock",
        "source/source.zip",
    ],
)
def test_modified_input_code_lock_or_archive_is_rejected(frozen, name):
    _, run, _ = frozen
    (run / "result.json").write_text("{}")
    finish_run(run, ["result.json"], status="completed", environments={})
    target = run / name
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="CHANGED"):
        verify_run(run)


def test_missing_result_and_failed_run_cannot_pass_verification(frozen):
    _, run, _ = frozen
    with pytest.raises(ValueError, match="INCOMPLETE"):
        verify_run(run)
    finish_run(run, [], status="failed", environments={}, error_code="CHILD_FAILED")
    with pytest.raises(ValueError, match="NOT_COMPLETED"):
        verify_run(run)


@pytest.mark.parametrize(
    "name",
    [
        "../outside.json",
        "/outside.json",
        "C:/outside.json",
        "x\\outside.json",
        "experiment-result.json",
    ],
)
def test_output_members_are_contained_and_control_files_reserved(frozen, name):
    _, run, _ = frozen
    with pytest.raises(ValueError, match="PATH"):
        finish_run(run, [name], status="completed", environments={})


def test_intact_bundle_can_move_without_original_checkout(frozen, tmp_path):
    repo, run, _ = frozen
    (run / "result.json").write_text("{}")
    finish_run(run, ["result.json"], status="completed", environments={})
    moved = tmp_path / "moved"
    shutil.copytree(run, moved)
    # The verifier reads retained code, not the original source checkout.
    (repo / "src/module.py").write_text("VALUE = 2\n")
    assert verify_run(moved)["status"] == "completed"


def test_existing_directory_is_not_overwritten(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        init_run(existing)
    assert (existing / "keep.txt").read_text() == "keep"


def test_changed_plan_metadata_is_detected(frozen):
    _, run, _ = frozen
    value = json.loads((run / "experiment-plan.json").read_text())
    value["parameters"]["fee_bps"] = 0
    (run / "experiment-plan.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="CHANGED"):
        finish_run(run, [], status="failed", environments={}, error_code="CHILD_FAILED")
