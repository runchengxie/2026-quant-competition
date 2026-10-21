"""Dispatch blocks changed inputs/code and never fabricates zero returns."""

import json
import pytest
from competition_tools.team.config import TeamConfig
from competition_tools.evaluation.study_plan import freeze_study
from competition_tools.evaluation.study_runner import run_study
from test_study_plan import crypto_manifest, identity, COSTS


def test_changed_code_blocks_planned_jobs_without_child(tmp_path, monkeypatch):
    manifest = crypto_manifest(tmp_path / "data")
    root = tmp_path / "plan"
    freeze_study(
        {
            "schema": "competition.evaluation_spec.v2",
            "manifests": [str(manifest)],
            "costs": COSTS,
        },
        root,
        code_identity=identity(tmp_path / "code"),
    )

    def forbidden(*a, **k):
        pytest.fail("Changed source must not execute a child")

    monkeypatch.setattr(
        "competition_tools.evaluation.study_runner.run_child", forbidden
    )
    result = run_study(TeamConfig(tmp_path, tmp_path / "envs"), root / "plan.json")
    crypto = [j for j in result["jobs"] if j["market"] == "crypto"]
    assert all(
        j["status"] == "blocked" and j["reason"] == "CODE_CHANGED" for j in crypto
    )
    assert all(j["metrics"] is None for j in crypto)


def test_altered_job_file_is_rejected_before_execution(tmp_path):
    manifest = crypto_manifest(tmp_path / "data")
    root = tmp_path / "plan"
    plan = freeze_study(
        {
            "schema": "competition.evaluation_spec.v2",
            "manifests": [str(manifest)],
            "costs": COSTS,
        },
        root,
        code_identity=identity(tmp_path / "code"),
    )
    path = root / "jobs" / (plan["jobs"][0]["job_id"] + ".json")
    value = json.loads(path.read_text())
    value["fee_bps"] = 999
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="FROZEN_JOB_CHANGED"):
        run_study(TeamConfig(tmp_path, tmp_path / "envs"), root / "plan.json")


def test_self_hashed_plan_cannot_use_a_job_id_as_an_external_path(tmp_path):
    from competition_tools.evaluation.study_plan import plan_hash

    manifest = crypto_manifest(tmp_path / "data")
    root = tmp_path / "plan"
    plan = freeze_study(
        {
            "schema": "competition.evaluation_spec.v2",
            "manifests": [str(manifest)],
            "costs": COSTS,
        },
        root,
        code_identity=identity(tmp_path / "code"),
    )
    plan["jobs"][0]["job_id"] = str(tmp_path / "outside")
    plan["plan_sha256"] = plan_hash(plan)
    for job in plan["jobs"]:
        job["plan_sha256"] = plan["plan_sha256"]
    (root / "plan.json").write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="INVALID_FROZEN_PLAN"):
        run_study(TeamConfig(tmp_path, tmp_path / "envs"), root / "plan.json")


def test_v2_module_command_freezes_before_reporting_short_history(tmp_path, capsys):
    from competition_tools.team.__main__ import main

    manifest = crypto_manifest(tmp_path / "data", days=300)
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "competition.evaluation_spec.v2",
                "manifests": [str(manifest)],
                "costs": COSTS,
            }
        )
    )
    config = tmp_path / "team.toml"
    config.write_text(
        f'schema_version="competition.team.v1"\ndata_root="{tmp_path.as_posix()}"\nenvironment_root="{tmp_path.as_posix()}/envs"\n'
    )
    assert (
        main(
            [
                "evaluate",
                "--config",
                str(config),
                "--spec",
                str(spec),
                "--output-root",
                str(tmp_path / "plan"),
            ]
        )
        == 2
    )
    value = json.loads(capsys.readouterr().out)
    assert value["issue_codes"] == ["EVALUATION_PARTIAL"]
    assert (tmp_path / "plan/plan.json").is_file()
    assert (tmp_path / "plan/run/study-results.json").is_file()
