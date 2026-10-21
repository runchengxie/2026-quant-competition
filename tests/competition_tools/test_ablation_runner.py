"""Runner integrity and a single elapsed-time budget across batches."""

import pytest
from competition_tools.evaluation import ablation_runner as runner
from competition_tools.evaluation.ablation_plan import freeze_ablation
from competition_tools.evaluation.study_identity import source_identity
from competition_tools.team.config import TeamConfig
from competition_tools.check_ablation_delivery import synthetic_spec
from test_ablation_source import fixture_repo


def frozen(tmp_path):
    root = fixture_repo(tmp_path / "source")
    spec = synthetic_spec(tmp_path / "inputs")
    plan = freeze_ablation(
        spec, tmp_path / "study", code_identity=source_identity(root)
    )
    return plan, tmp_path / "study/plan.json", TeamConfig(tmp_path, tmp_path / "envs")


def test_shared_deadline_is_not_reset_for_second_batch():
    jobs = list(range(678))
    batches = list(runner.batches(jobs))
    assert list(map(len, batches)) == [384, 294]
    assert runner.remaining_seconds(10, now=3611) == -1
    assert runner.remaining_seconds(10, now=20) == 3590


def test_wrong_installed_leaf_is_blocked(tmp_path):
    _, p, c = frozen(tmp_path)
    out = runner.run_ablation(c, p)
    assert all(r["status"] == "blocked" and r["metrics"] is None for r in out["jobs"])
    assert any(r["reason"] == "CODE_CHANGED" for r in out["jobs"])


def test_changed_frozen_job_is_rejected_before_execution(tmp_path):
    plan, p, c = frozen(tmp_path)
    job = plan["jobs"][0]
    path = p.parent / "jobs" / (job["job_id"] + ".json")
    path.write_text("{}")
    with pytest.raises(ValueError, match="FROZEN_JOB_CHANGED"):
        runner.run_ablation(c, p)


def test_shared_timeout_does_not_retry_or_fabricate_values(tmp_path, monkeypatch):
    _, p, c = frozen(tmp_path)
    monkeypatch.setattr(runner, "remaining_seconds", lambda *a, **k: -1)
    monkeypatch.setattr(
        runner, "run_child", lambda *a, **k: pytest.fail("No expired child")
    )
    out = runner.run_ablation(c, p)
    assert any(
        r["reason"] == "TIME_BUDGET" and r["metrics"] is None for r in out["jobs"]
    )


def test_post_run_input_change_invalidates_completed_metrics():
    records = [
        {
            "market": "US",
            "status": "completed",
            "metrics": {"net_return": 1},
            "benchmark_excess_return": 1,
            "baseline_job_id": "a",
            "paired_net_change": 1,
            "paired_drawdown_change": 1,
            "paired_turnover_change": 1,
            "paired_exposure_change": 1,
        }
    ]
    runner.invalidate_market(records, "US", "INPUT_CHANGED_POST_RUN")
    assert records[0]["status"] == "blocked" and records[0]["metrics"] is None
    assert (
        records[0]["paired_net_change"] is None
        and records[0]["benchmark_excess_return"] is None
    )


def test_missing_market_benchmark_and_baseline_remain_null():
    records = [
        {
            "job_id": "a",
            "market": "US",
            "status": "completed",
            "strategy": "sma_cross",
            "variant_id": "weekly",
            "fee_bps": 20,
            "fold": {"start": "2026-01-01", "end": "2026-03-01"},
            "metrics": {
                "net_return": 0.04,
                "max_drawdown": 0.1,
                "mean_daily_turnover": 0.02,
                "mean_exposure": 0.5,
            },
        }
    ]
    runner.pair_records(records)
    assert records[0]["benchmark_excess_return"] is None
    assert records[0]["paired_net_change"] is None


def test_wrong_leaf_location_is_rejected_even_when_bytes_match(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json

    plan, _, c = frozen(tmp_path)
    job = next(j for j in plan["jobs"] if j["status"] == "planned")
    monkeypatch.setattr(
        runner, "source_hash", lambda root: plan["code_identity"]["source_sha256"]
    )
    monkeypatch.setattr(
        runner,
        "run_child",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [str(tmp_path / "other/leaf.py"), job["expected_leaf_sha256"]]
            ),
        ),
    )
    with pytest.raises(ValueError, match="CODE_CHANGED"):
        runner._verify_runtime(c, plan, job, 10)


def test_interruption_blocks_remaining_jobs_without_retry(tmp_path, monkeypatch):
    plan, p, c = frozen(tmp_path)
    calls = []
    monkeypatch.setattr(
        runner, "source_hash", lambda root: plan["code_identity"]["source_sha256"]
    )
    monkeypatch.setattr(runner, "_verify_runtime", lambda *a: None)

    def child(*args, **kwargs):
        calls.append(args)
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_child", child)
    out = runner.run_ablation(c, p)
    assert len(calls) == 1
    assert all(r["metrics"] is None for r in out["jobs"])
    assert all(r["reason"] == "INTERRUPTED" for r in out["jobs"] if "strategy" in r)


@pytest.mark.parametrize("field", ["origin", "code_identity", "catalog_sha256"])
def test_self_hashed_plan_cannot_diverge_from_retained_identity(tmp_path, field):
    import json
    from competition_tools.evaluation.ablation_plan import ablation_plan_hash

    plan, p, _ = frozen(tmp_path)
    if field == "origin":
        plan[field]["probe_protocol_sha256"] = "f" * 64
    elif field == "code_identity":
        plan[field]["source_sha256"] = "f" * 64
    else:
        plan[field] = "f" * 64
    plan["plan_sha256"] = ablation_plan_hash(plan)
    for j in plan["jobs"]:
        j["plan_sha256"] = plan["plan_sha256"]
        (p.parent / "jobs" / (j["job_id"] + ".json")).write_text(json.dumps(j))
    p.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        runner.verify_plan(p)


def test_boolean_signal_parameter_is_not_numeric_zero(tmp_path):
    from competition_tools.evaluation.ablation_plan import (
        job_hash,
        validate_ablation_job,
    )

    plan, _, _ = frozen(tmp_path)
    job = next(j for j in plan["jobs"] if j.get("strategy") == "momentum_20d")
    job["parameters"]["min_momentum"] = False
    job["job_id"] = job_hash(job)
    with pytest.raises(ValueError):
        validate_ablation_job(job)
