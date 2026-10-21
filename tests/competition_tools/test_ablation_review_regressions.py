"""Independent review regressions: period facts, strict types and final guards."""

import copy
import json
import math
from statistics import mean, stdev
from types import SimpleNamespace
import pytest
from competition_tools.evaluation import ablation_runner as runner
from competition_tools.evaluation.ablation_plan import EXTRA, job_hash
from competition_tools.datasets.storage import digest
from test_ablation_runner import frozen


def artifact_fixture(tmp_path, fee=0):
    plan, _, _ = frozen(tmp_path)
    job = copy.deepcopy(
        next(
            j
            for j in plan["jobs"]
            if j.get("market") == "crypto"
            and j.get("strategy") == "equal_weight"
            and j.get("fee_bps") == 0
        )
    )
    job["fee_bps"] = fee
    job["job_id"] = job_hash(job)
    series = []
    for charged in [True, False]:
        factor = 1 / (1 + fee / 10000) if charged else 1.0
        rows = []
        for i, day in enumerate(job["dates"][252:]):
            rows.append(
                dict(
                    date=day,
                    equity=factor,
                    cash=0.0,
                    positions={
                        p: factor / len(job["products"]) for p in job["products"]
                    },
                    weights={p: 1 / len(job["products"]) for p in job["products"]},
                    turnover=(factor if i == 0 else 0.0),
                    cost=(1 - factor if i == 0 else 0.0),
                    net_return=(factor - 1 if i == 0 else 0.0),
                    exposure=1.0,
                )
            )
        series.append(rows)
    net, gross = series
    returns = [p["net_return"] for p in net]
    dev = stdev(returns)
    metrics = dict(
        periods=len(net),
        net_return=net[-1]["equity"] - 1,
        gross_return=0.0,
        cost_drag=1 - net[-1]["equity"],
        volatility=dev * math.sqrt(365),
        sharpe=mean(returns) / dev * math.sqrt(365) if dev else None,
        max_drawdown=1 - net[-1]["equity"],
        turnover=sum(p["turnover"] for p in net),
        total_costs=sum(p["cost"] for p in net),
        mean_daily_turnover=mean(p["turnover"] for p in net),
        mean_exposure=1.0,
        flat_days=0,
    )
    fields = (
        "job_id plan_sha256 manifest_sha256 code_commit market quote_currency strategy parameters fee_bps products fold benchmark".split()
        + list(EXTRA)
    )
    result = {k: job[k] for k in fields}
    result.update(
        schema="competition.daily_study_result.v2",
        code_sha256=job["expected_leaf_sha256"],
        start=job["fold"]["start"],
        end=job["fold"]["end"],
        methods=runner.methods_for(job),
        metrics=metrics,
        accepted_research=False,
    )
    periods = dict(
        schema="competition.daily_study_periods.v2",
        job_id=job["job_id"],
        net=net,
        gross=gross,
    )
    destination = tmp_path / "artifact"
    destination.mkdir()
    return job, result, periods, destination


def write_artifact(result, periods, destination):
    p = destination / "periods.json"
    p.write_text(json.dumps(periods))
    result["artifacts"] = [dict(path=p.name, bytes=p.stat().st_size, sha256=digest(p))]
    (destination / "result.json").write_text(json.dumps(result))


@pytest.mark.parametrize("corruption", ["exposure", "weights", "cost", "gross_cost"])
def test_corrupt_period_accounting_facts_are_rejected(tmp_path, corruption):
    job, result, periods, out = artifact_fixture(tmp_path, fee=0)
    write_artifact(result, periods, out)
    runner.verify_ablation_result(job, out)
    if corruption == "exposure":
        for p in periods["net"]:
            p["exposure"] = 0.0
            p["weights"] = {k: 0.0 for k in p["weights"]}
        result["metrics"].update(mean_exposure=0.0, flat_days=89)
    elif corruption == "weights":
        for p in periods["net"]:
            p["weights"] = {k: 0.0 for k in p["weights"]}
    elif corruption == "cost":
        periods["net"][0]["cost"] = 0.1
        result["metrics"]["total_costs"] = 0.1
    else:
        periods["gross"][0]["cost"] = 0.1
    write_artifact(result, periods, out)
    with pytest.raises(ValueError):
        runner.verify_ablation_result(job, out)


@pytest.mark.parametrize("field", ["fee", "method", "origin"])
def test_result_boolean_metadata_is_not_numeric_identity(tmp_path, field):
    job, result, periods, out = artifact_fixture(tmp_path)
    if field == "fee":
        result["fee_bps"] = False
    elif field == "method":
        result["methods"]["signal_lag_periods"] = True
    else:
        result["origin"] = dict(result["origin"], retrospective=1)
    write_artifact(result, periods, out)
    with pytest.raises(ValueError):
        runner.verify_ablation_result(job, out)


def fake_child_fixture(tmp_path, monkeypatch):
    plan, path, config = frozen(tmp_path)
    result = tmp_path / "result.json"
    result.write_text("{}")
    metrics = dict(
        net_return=0.0, max_drawdown=0.0, mean_daily_turnover=0.0, mean_exposure=1.0
    )
    monkeypatch.setattr(runner, "_verify_runtime", lambda *a: None)
    monkeypatch.setattr(
        runner,
        "run_child",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner, "verify_ablation_result", lambda *a: ({"metrics": metrics}, result)
    )
    return plan, path, config, metrics, result


def test_final_unreadable_source_invalidates_and_persists_all_records(
    tmp_path, monkeypatch
):
    plan, path, config, _, _ = fake_child_fixture(tmp_path, monkeypatch)
    calls = [0]

    def source(root):
        calls[0] += 1
        if calls[0] > 2:
            raise ValueError("SOURCE_ROOT_REQUIRED")
        return plan["code_identity"]["source_sha256"]

    monkeypatch.setattr(runner, "source_hash", source)
    result = runner.run_ablation(config, path)
    assert len(result["jobs"]) == len(plan["jobs"])
    assert all(
        r["metrics"] is None and r["paired_net_change"] is None for r in result["jobs"]
    )
    assert all(r["reason"] == "CODE_CHANGED" for r in result["jobs"] if "strategy" in r)
    assert json.loads((path.parent / "run/study-results.json").read_text()) == result


def test_post_verification_deadline_keeps_late_job_null(tmp_path, monkeypatch):
    plan, path, config, metrics, result_path = fake_child_fixture(tmp_path, monkeypatch)
    clock = {"now": 0.0}
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        runner, "source_hash", lambda root: plan["code_identity"]["source_sha256"]
    )

    def child(*a, **k):
        clock["now"] = 3599.9
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def verify(*a):
        clock["now"] = 3601.0
        return {"metrics": metrics}, result_path

    monkeypatch.setattr(runner, "run_child", child)
    monkeypatch.setattr(runner, "verify_ablation_result", verify)
    result = runner.run_ablation(config, path)
    assert all(r["metrics"] is None for r in result["jobs"])
    assert all(r["reason"] == "TIME_BUDGET" for r in result["jobs"] if "strategy" in r)


def test_runtime_probe_cannot_start_after_source_check_uses_budget(
    tmp_path, monkeypatch
):
    plan, _, config = frozen(tmp_path)
    clock = {"now": 0.0}
    job = next(j for j in plan["jobs"] if j["status"] == "planned")
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock["now"])

    def source(root):
        clock["now"] = 2.0
        return plan["code_identity"]["source_sha256"]

    monkeypatch.setattr(runner, "source_hash", source)
    monkeypatch.setattr(
        runner, "run_child", lambda *a, **k: pytest.fail("Expired runtime probe")
    )
    with pytest.raises(ValueError, match="TIME_BUDGET"):
        runner._verify_runtime(config, plan, job, 1.0)
