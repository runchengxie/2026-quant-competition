"""Root verification must reconstruct facts and retain blocked denominators."""

import copy
from pathlib import Path

import pytest

from competition_tools.evaluation.controls import runner
from competition_tools.evaluation.controls.catalog import (
    ARMS,
    BUDGET,
    COSTS,
    CATALOG_SHA256,
    arm_spec,
)
from competition_tools.evaluation.controls.contracts import JOB_KEYS, job_hash
from competition_tools.evaluation.controls.plan import freeze_controls
from competition_tools.evaluation.study_identity import source_identity
from competition_tools.datasets.storage import digest, write_json
from competition_tools.team.config import TeamConfig


def fixture_plan(tmp_path):
    from test_ablation_source import fixture_repo
    from competition_tools.check_ablation_delivery import synthetic_spec

    source = fixture_repo(tmp_path / "source")
    old = synthetic_spec(tmp_path / "inputs")
    manifests = dict(zip(("US", "crypto"), old["manifests"], strict=True))
    spec = dict(
        schema="competition.strategy_controls_spec.v1",
        manifests=manifests,
        expected_input_hashes={m: digest(Path(p)) for m, p in manifests.items()},
        arms=copy.deepcopy(ARMS),
        costs=copy.deepcopy(COSTS),
        role="retrospective",
        accepted_research=False,
        budget=copy.deepcopy(BUDGET),
    )
    plan = freeze_controls(
        spec, tmp_path / "frozen", code_identity=source_identity(source)
    )
    return plan, tmp_path / "frozen/plan.json"


def artifact_fixture(tmp_path):
    from test_ablation_review_regressions import artifact_fixture as old_fixture

    old, value, periods, destination = old_fixture(tmp_path, fee=10)
    job = {k: copy.deepcopy(v) for k, v in old.items() if k in JOB_KEYS}
    policy = arm_spec("crypto", "ew_legacy")
    job.update(
        schema="competition.strategy_controls_job.v1",
        arm_id="ew_legacy",
        parameters=policy["parameters"],
        evidence_role=policy["role"],
        catalog_sha256=CATALOG_SHA256,
    )
    job["job_id"] = job_hash(job)
    periods.update(
        schema="competition.strategy_controls_periods.v1",
        job_id=job["job_id"],
        plan_sha256=job["plan_sha256"],
    )
    result = {
        k: job[k]
        for k in "job_id plan_sha256 manifest_sha256 expected_leaf_sha256 code_commit market arm_id fee_bps quote_currency accepted_research".split()
    }
    result.update(
        schema="competition.strategy_controls_result.v1",
        status="completed",
        metrics=value["metrics"],
        diagnostics={},
        artifacts=[],
        issue_codes=[],
    )
    write_artifact(destination, result, periods)
    return job, result, periods, destination


def write_artifact(destination, result, periods):
    write_json(destination / "periods.json", periods)
    result["artifacts"] = [
        dict(
            path="periods.json",
            bytes=(destination / "periods.json").stat().st_size,
            sha256=digest(destination / "periods.json"),
        )
    ]
    write_json(destination / "result.json", result)


def test_batch_and_elapsed_caps_are_shared():
    assert [len(b) for b in runner.batches(list(range(512)))] == [384, 128]
    with pytest.raises(ValueError, match="CONTROLS_JOB_BUDGET"):
        runner.batches(list(range(513)))
    assert runner.remaining_seconds(10, spent=20, now=3610) == -20


@pytest.mark.parametrize(
    "corruption", [None, "metrics", "periods", "fee", "identity", "private"]
)
def test_period_economics_and_identity_are_verified(tmp_path, corruption):
    job, result, periods, destination = artifact_fixture(tmp_path)
    if corruption == "metrics":
        result["metrics"]["net_return"] += 0.1
    elif corruption == "periods":
        periods["net"][0]["cost"] += 0.01
    elif corruption == "fee":
        result["fee_bps"] = 25
    elif corruption == "identity":
        periods["plan_sha256"] = "0" * 64
    elif corruption == "private":
        result["account"] = "must-not-be-ignored"
    write_artifact(destination, result, periods)
    if corruption:
        with pytest.raises(ValueError):
            runner.verify_control_result(job, destination / "result.json")
    else:
        assert (
            runner.verify_control_result(job, destination / "result.json")["metrics"]
            == result["metrics"]
        )


def test_failed_child_keeps_all_jobs_and_strips_credentials(tmp_path, monkeypatch):
    plan, path = fixture_plan(tmp_path)
    monkeypatch.setenv("COINPAPRIKA_API_KEY", "fixture-secret")
    monkeypatch.setenv("DEXPAPRIKA_API_KEY", "fixture-secret")
    calls = []

    def failed(argv, *, environment, timeout):
        assert not any(
            k.upper().endswith(("API_KEY", "TOKEN", "PASSWORD")) for k in environment
        )
        assert timeout <= 3600
        calls.append(argv)
        raise OSError("private exception must not leak")

    monkeypatch.setattr(runner, "run_child", failed)
    result = runner.run_controls(TeamConfig(tmp_path / "data", tmp_path / "envs"), path)
    assert len(result["jobs"]) == len(plan["jobs"]) == 36
    assert all(
        j["status"] == "blocked" and j["metrics"] is None for j in result["jobs"]
    )
    assert len(calls) == 2
    assert "private exception" not in str(result)
    assert (
        runner.run_controls(TeamConfig(tmp_path / "data", tmp_path / "envs"), path)
        == result
    )
    assert len(calls) == 2


def test_changed_frozen_input_blocks_before_child(tmp_path, monkeypatch):
    plan, path = fixture_plan(tmp_path)
    manifest = Path(plan["inputs"]["US"]["manifest"])
    manifest.write_text("{}")
    monkeypatch.setattr(
        runner, "run_child", lambda *a, **k: pytest.fail("changed input reached child")
    )
    with pytest.raises(ValueError):
        runner.run_controls(TeamConfig(tmp_path / "data", tmp_path / "envs"), path)


def test_checkpoint_cost_is_charged_before_launching_child(tmp_path, monkeypatch):
    _, path = fixture_plan(tmp_path)
    clock = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    original = runner._files
    checks = []

    def expensive(root):
        records = original(root)
        checks.append(root)
        if len(checks) == 2:
            clock[0] = 3601
        return records

    monkeypatch.setattr(runner, "_files", expensive)
    monkeypatch.setattr(
        runner,
        "run_child",
        lambda *a, **k: pytest.fail("deadline passed during checkpoint"),
    )
    result = runner.run_controls(TeamConfig(tmp_path / "data", tmp_path / "envs"), path)
    assert all(j["status"] == "blocked" for j in result["jobs"])


def test_added_nested_state_file_is_not_ignored(tmp_path, monkeypatch):
    _, path = fixture_plan(tmp_path)
    monkeypatch.setattr(
        runner, "run_child", lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))
    )
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    runner.run_controls(config, path)
    extra = path.parent / "run/extra/state.json"
    extra.parent.mkdir()
    extra.write_text("{}")
    with pytest.raises(ValueError):
        runner.run_controls(config, path)


@pytest.mark.parametrize("elapsed", [float("nan"), float("inf")])
def test_unknown_nonfinite_spend_cannot_resume(tmp_path, monkeypatch, elapsed):
    _, path = fixture_plan(tmp_path)
    monkeypatch.setattr(runner, "run_child", lambda *a, **k: None)
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    runner.run_controls(config, path)
    import json

    state_path = path.parent / "run/state.json"
    state = json.loads(state_path.read_text())
    state["elapsed_seconds"] = elapsed
    state_path.write_text(json.dumps(state))
    state_path.with_suffix(".sha256").write_text(digest(state_path))
    with pytest.raises(ValueError):
        runner.run_controls(config, path)


@pytest.mark.parametrize("corruption", ["extra", "identity", "status", "path"])
def test_results_index_contract_is_not_ignored(tmp_path, corruption):
    plan, _ = fixture_plan(tmp_path)
    rows = [runner._record(j) for j in plan["jobs"]]
    result = dict(
        schema="competition.strategy_controls_results.v1",
        plan_sha256=plan["plan_sha256"],
        status="partial",
        elapsed_seconds=1,
        jobs=rows,
    )
    if corruption == "extra":
        rows[0]["account"] = "private"
    elif corruption == "identity":
        rows[0]["arm_id"] = "another-arm"
    elif corruption == "status":
        rows[0]["status"] = "invented"
    else:
        rows[0]["result_path"] = "../outside/result.json"
    from competition_tools.evaluation.controls.verification import (
        validate_results_index,
    )

    with pytest.raises(ValueError):
        validate_results_index(plan, result)


def test_resume_preserves_spend_and_never_retries_interrupted_batch(
    tmp_path, monkeypatch
):
    _, path = fixture_plan(tmp_path)
    clock = [0.0]
    calls = []
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])

    def interrupted(argv, **kwargs):
        calls.append(argv)
        clock[0] = 3599.0
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_child", interrupted)
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    first = runner.run_controls(config, path)
    assert sum(r["reason"] == "NOT_RUN" for r in first["jobs"]) == 24

    def remaining(argv, **kwargs):
        calls.append(argv)
        assert kwargs["timeout"] == 1
        assert "crypto_mm.daily.controls_cli" in argv
        clock[0] += 1

    monkeypatch.setattr(runner, "run_child", remaining)
    second = runner.run_controls(config, path)
    assert len(calls) == 2
    assert second["elapsed_seconds"] == 3600
    assert all(r["reason"] != "NOT_RUN" for r in second["jobs"])
    runner.run_controls(config, path)
    assert len(calls) == 2
