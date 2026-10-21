"""Bounded independent CLI dispatch and verified v2 study artifacts."""

import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest, write_json, verify_manifest
from competition_tools.team.config import TeamConfig
from competition_tools.team.processes import interpreter, child_environment, run_child
from .study_identity import source_hash, canonical_hash
from .study_plan import PARAMETERS
from .study_runner import _verify_consumed, _finite
from .ablation_plan import validate_ablation_job, ablation_plan_hash, BUDGET, EXTRA
from .ablation_source import verify_source_snapshot
from .ablation_catalog import CATALOG_SHA256

METRIC_KEYS = set(
    "periods net_return gross_return cost_drag volatility sharpe max_drawdown turnover total_costs mean_daily_turnover mean_exposure flat_days".split()
)
PAIRED = {
    "paired_net_change": "net_return",
    "paired_drawdown_change": "max_drawdown",
    "paired_turnover_change": "mean_daily_turnover",
    "paired_exposure_change": "mean_exposure",
}


def batches(jobs):
    for i in range(0, len(jobs), 384):
        yield jobs[i : i + 384]


def remaining_seconds(start, *, now=None):
    return 3600 - ((time.monotonic() if now is None else now) - start)


def methods_for(job):
    hold = job["strategy"] in {"buy_hold", "benchmark_buy_hold"} or (
        job["market"] == "crypto" and job["strategy"] == "equal_weight"
    )
    return dict(
        method_id=job["market"].lower()
        + "."
        + job["strategy"]
        + "."
        + job["variant_id"]
        + ".self_financing_daily.v1",
        strategy=job["strategy"],
        signal_parameters=PARAMETERS[job["strategy"]],
        signal_lag_periods=1,
        rebalance=("buy_hold" if hold else "daily_target_weights")
        if job["variant_id"] == "baseline"
        else job["variant_id"],
        execution_assumption="lagged_close_proxy",
        warmup_periods=252,
        scoring_periods=job["fold"]["scoring_periods"],
        fold_initialization="independent_cash",
        cost_model="self_financing_oneway_bps",
        terminal_liquidation=False,
        retrospective=True,
        **{k: job[k] for k in ["variant_id", "variant_parameters", "evidence_role"]},
    )


def _verify_period_metrics(job, value, periods):
    if (
        set(periods) != {"schema", "job_id", "net", "gross"}
        or periods["schema"] != "competition.daily_study_periods.v2"
        or periods["job_id"] != job["job_id"]
    ):
        raise ValueError("INVALID_STUDY_ARTIFACT")
    net, gross = periods["net"], periods["gross"]
    dates = job["dates"][252:]
    if len(net) != len(dates) or len(gross) != len(dates) or not _finite(periods):
        raise ValueError("INVALID_STUDY_ARTIFACT")
    peak = 1.0
    dd = 0.0
    for series, fee_bps in [(net, job["fee_bps"]), (gross, 0)]:
        before = 1.0
        for expected, p in zip(dates, series):
            if (
                set(p)
                != {
                    "date",
                    "equity",
                    "cash",
                    "positions",
                    "weights",
                    "turnover",
                    "cost",
                    "net_return",
                    "exposure",
                }
                or p["date"] != expected
            ):
                raise ValueError("INVALID_STUDY_ARTIFACT")
            for key in ["equity", "cash", "turnover", "cost", "net_return", "exposure"]:
                if type(p[key]) not in (int, float):
                    raise ValueError("INVALID_STUDY_ARTIFACT")
            if (
                p["equity"] <= 0
                or p["cash"] < -1e-12
                or p["turnover"] < 0
                or p["cost"] < 0
                or not 0 <= p["exposure"] <= 1 + 1e-12
                or set(p["positions"]) != set(job["products"])
                or set(p["weights"]) != set(job["products"])
            ):
                raise ValueError("INVALID_STUDY_ARTIFACT")
            if any(
                type(x) not in (int, float) or x < 0
                for x in [*p["positions"].values(), *p["weights"].values()]
            ):
                raise ValueError("INVALID_STUDY_ARTIFACT")
            if not math.isclose(
                p["equity"] / before - 1, p["net_return"], rel_tol=0, abs_tol=1e-10
            ) or not math.isclose(
                p["cash"] + sum(p["positions"].values()),
                p["equity"],
                rel_tol=0,
                abs_tol=1e-10,
            ):
                raise ValueError("INVALID_STUDY_ARTIFACT")
            weights = {
                product: value / p["equity"]
                for product, value in p["positions"].items()
            }
            if (
                any(
                    not math.isclose(
                        p["weights"][product], weight, rel_tol=0, abs_tol=1e-10
                    )
                    for product, weight in weights.items()
                )
                or not math.isclose(
                    p["exposure"], sum(weights.values()), rel_tol=0, abs_tol=1e-10
                )
                or not math.isclose(
                    p["cost"],
                    fee_bps / 10000 * p["turnover"] * before,
                    rel_tol=0,
                    abs_tol=1e-10,
                )
            ):
                raise ValueError("INVALID_STUDY_ARTIFACT")
            before = p["equity"]
    for p in net:
        peak = max(peak, p["equity"])
        dd = max(dd, 1 - p["equity"] / peak)
    returns = [p["net_return"] for p in net]
    dev = stdev(returns) if len(net) > 1 else 0
    annual = 365 if job["market"] == "crypto" else 252
    expected = dict(
        periods=len(net),
        net_return=net[-1]["equity"] - 1,
        gross_return=gross[-1]["equity"] - 1,
        cost_drag=gross[-1]["equity"] - net[-1]["equity"],
        volatility=dev * math.sqrt(annual),
        sharpe=mean(returns) / dev * math.sqrt(annual) if dev else None,
        max_drawdown=dd,
        turnover=sum(p["turnover"] for p in net),
        total_costs=sum(p["cost"] for p in net),
        mean_daily_turnover=mean(p["turnover"] for p in net),
        mean_exposure=mean(p["exposure"] for p in net),
        flat_days=sum(p["exposure"] <= 1e-12 and p["turnover"] <= 1e-12 for p in net),
    )
    m = value["metrics"]
    if set(m) != METRIC_KEYS:
        raise ValueError("INVALID_STUDY_RESULT")
    for k, v in expected.items():
        if v is None:
            if m[k] is not None:
                raise ValueError("INVALID_STUDY_RESULT")
        elif (
            type(m[k]) not in (int, float)
            or not math.isclose(v, m[k], rel_tol=0, abs_tol=1e-10)
            or (k in {"periods", "flat_days"} and type(m[k]) is not int)
        ):
            raise ValueError("INVALID_STUDY_RESULT")


def verify_ablation_result(job: dict, destination: Path) -> tuple[dict, Path]:
    validate_ablation_job(job)
    path = safe_path(destination / "result.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    pairs = (
        "job_id plan_sha256 manifest_sha256 code_commit market quote_currency strategy parameters fee_bps products fold benchmark".split()
        + list(EXTRA)
    )
    expected_keys = set(pairs) | {
        "schema",
        "code_sha256",
        "start",
        "end",
        "methods",
        "metrics",
        "accepted_research",
        "artifacts",
    }
    if (
        set(value) != expected_keys
        or value["schema"] != "competition.daily_study_result.v2"
        or not _finite(value)
        or value["accepted_research"] is not False
        or any(canonical_hash(value[k]) != canonical_hash(job[k]) for k in pairs)
        or value["code_sha256"] != job["expected_leaf_sha256"]
        or value["start"] != job["fold"]["start"]
        or value["end"] != job["fold"]["end"]
        or canonical_hash(value["methods"]) != canonical_hash(methods_for(job))
    ):
        raise ValueError("INVALID_STUDY_RESULT")
    artifacts = value["artifacts"]
    if (
        not isinstance(artifacts, list)
        or len(artifacts) != 1
        or set(artifacts[0]) != {"path", "sha256", "bytes"}
        or artifacts[0]["path"] != "periods.json"
        or type(artifacts[0]["bytes"]) is not int
    ):
        raise ValueError("INVALID_STUDY_ARTIFACT")
    target = safe_path(destination / "periods.json")
    if (
        target.stat().st_size != artifacts[0]["bytes"]
        or digest(target) != artifacts[0]["sha256"]
    ):
        raise ValueError("INVALID_STUDY_ARTIFACT")
    _verify_period_metrics(job, value, json.loads(target.read_text(encoding="utf-8")))
    return value, path


def verify_plan(plan_path):
    p = safe_path(plan_path)
    plan = json.loads(p.read_text(encoding="utf-8"))
    if (
        plan.get("schema") != "competition.study_plan.v2"
        or plan.get("plan_sha256") != ablation_plan_hash(plan)
        or plan["budget"] != BUDGET
        or not 1 <= len(plan["jobs"]) <= 768
        or len({j["job_id"] for j in plan["jobs"]}) != len(plan["jobs"])
    ):
        raise ValueError("INVALID_FROZEN_PLAN")
    verify_source_snapshot(plan["source_receipt"])
    if (
        set(plan)
        != {
            "schema",
            "plan_sha256",
            "code_identity",
            "source_receipt",
            "costs",
            "inputs",
            "jobs",
            "retrospective",
            "selection",
            "budget",
            "accepted_research",
            "origin",
            "catalog_sha256",
        }
        or plan["catalog_sha256"] != CATALOG_SHA256
        or plan["retrospective"] is not True
        or plan["accepted_research"] is not False
    ):
        raise ValueError("INVALID_FROZEN_PLAN")
    if plan["code_identity"] != {
        k: plan["source_receipt"][k] for k in ["commit", "source_root", "source_sha256"]
    }:
        raise ValueError("INVALID_FROZEN_PLAN")
    for j in plan["jobs"]:
        validate_ablation_job(j)
        if j["status"] == "planned" and (
            canonical_hash(j["origin"]) != canonical_hash(plan["origin"])
            or j["code_commit"] != plan["code_identity"]["commit"]
        ):
            raise ValueError("INVALID_FROZEN_PLAN")
        if (
            j["plan_sha256"] != plan["plan_sha256"]
            or json.loads(
                safe_path(p.parent / "jobs" / (j["job_id"] + ".json")).read_text(
                    encoding="utf-8"
                )
            )
            != j
        ):
            raise ValueError("FROZEN_JOB_CHANGED")
    return plan


def _source_matches(root, expected):
    try:
        return source_hash(root) == expected
    except (OSError, ValueError):
        return False


def _verify_runtime(config, plan, job, remaining):
    started = time.monotonic()
    root = Path(__file__).resolve().parents[3]
    if not _source_matches(root, plan["code_identity"]["source_sha256"]):
        raise ValueError("CODE_CHANGED")
    module = (
        "crypto_mm.daily.study_inputs"
        if job["market"] == "crypto"
        else "equity_lab.study.inputs"
    )
    command = [
        str(interpreter(config, job["project"])),
        "-c",
        f"import json; import {module} as m; print(json.dumps([m.__file__,m._source_hash()]))",
    ]
    remaining -= time.monotonic() - started
    if remaining <= 0:
        raise ValueError("TIME_BUDGET")
    child = run_child(command, environment=child_environment(config), timeout=remaining)
    expected = root / "research" / job["project"] / "src"
    if child.returncode:
        raise ValueError("CODE_CHANGED")
    location, sha = json.loads(child.stdout)
    if (
        not Path(location).resolve().is_relative_to(expected.resolve())
        or sha != job["expected_leaf_sha256"]
    ):
        raise ValueError("CODE_CHANGED")


def invalidate_market(records, market, reason):
    for r in records:
        if r["market"] == market and r["status"] == "completed":
            r.update(
                status="blocked",
                reason=reason,
                metrics=None,
                benchmark_excess_return=None,
                baseline_job_id=None,
                **{k: None for k in PAIRED},
            )


def pair_records(records):
    def key(r):
        return (r["market"], r["fee_bps"], r["fold"]["start"], r["fold"]["end"])

    completed = [r for r in records if r["status"] == "completed"]
    baselines = {
        (key(r), r["strategy"]): r for r in completed if r["variant_id"] == "baseline"
    }
    for r in records:
        r.update(
            benchmark_excess_return=None,
            baseline_job_id=None,
            **{k: None for k in PAIRED},
        )
    for r in completed:
        base = baselines.get((key(r), r["strategy"]))
        benchmark = baselines.get(
            (
                key(r),
                "equal_weight" if r["market"] == "crypto" else "benchmark_buy_hold",
            )
        )
        if base is not None:
            r.update(
                baseline_job_id=base["job_id"],
                **{
                    name: r["metrics"][metric] - base["metrics"][metric]
                    for name, metric in PAIRED.items()
                },
            )
        if benchmark is not None:
            r["benchmark_excess_return"] = (
                r["metrics"]["net_return"] - benchmark["metrics"]["net_return"]
            )


def run_ablation(config: TeamConfig, plan_path: Path) -> dict:
    plan_path = safe_path(plan_path)
    plan = verify_plan(plan_path)
    output = safe_path(plan_path.parent / "run")
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    records = []
    interrupted = False
    runtime_verified = set()

    def aggregate():
        return dict(
            schema="competition.study_results.v2",
            plan_path=str(plan_path),
            observed_at=datetime.now(timezone.utc).isoformat(),
            plan_sha256=plan["plan_sha256"],
            code_commit=plan["code_identity"]["commit"],
            jobs=records,
            accepted_research=False,
        )

    for batch in batches(plan["jobs"]):
        for job in batch:
            record = dict(
                job_id=job["job_id"],
                market=job["market"],
                status="blocked",
                reason=job.get("reason"),
                metrics=None,
                result_path=None,
                result_sha256=None,
                benchmark_excess_return=None,
                blockers=[],
            )
            if job["status"] == "planned":
                record.update(
                    {
                        k: job[k]
                        for k in [
                            "strategy",
                            "fee_bps",
                            "fold",
                            "quote_currency",
                            *EXTRA,
                        ]
                    }
                )
                try:
                    if interrupted:
                        raise ValueError("INTERRUPTED")
                    remaining = remaining_seconds(started)
                    if remaining <= 0:
                        raise ValueError("TIME_BUDGET")
                    root = Path(__file__).resolve().parents[3]
                    if not _source_matches(
                        root, plan["code_identity"]["source_sha256"]
                    ):
                        raise ValueError("CODE_CHANGED")
                    if job["project"] not in runtime_verified:
                        _verify_runtime(config, plan, job, remaining_seconds(started))
                        runtime_verified.add(job["project"])
                    _verify_consumed(job)
                    destination = output / job["job_id"]
                    module = (
                        "crypto_mm.daily.study_cli"
                        if job["project"] == "crypto-mm"
                        else "equity_lab.study"
                    )
                    command = [
                        str(interpreter(config, job["project"])),
                        "-m",
                        module,
                        "--job",
                        str(plan_path.parent / "jobs" / (job["job_id"] + ".json")),
                        "--output-root",
                        str(destination),
                    ]
                    remaining = remaining_seconds(started)
                    if remaining <= 0:
                        raise ValueError("TIME_BUDGET")
                    child = run_child(
                        command,
                        environment=child_environment(config),
                        timeout=remaining,
                    )
                    (output / (job["job_id"] + ".log")).write_text(
                        child.stdout + "\n" + child.stderr, encoding="utf-8"
                    )
                    if child.returncode:
                        record.update(status="failed", reason="STUDY_CHILD_FAILED")
                    else:
                        result, path = verify_ablation_result(job, destination)
                        _verify_consumed(job)
                        if not _source_matches(
                            root, plan["code_identity"]["source_sha256"]
                        ):
                            raise ValueError("CODE_CHANGED")
                        result_sha256 = digest(path)
                        if remaining_seconds(started) <= 0:
                            raise ValueError("TIME_BUDGET")
                        record.update(
                            status="completed",
                            reason=None,
                            metrics=result["metrics"],
                            result_path=str(path),
                            result_sha256=result_sha256,
                        )
                except KeyboardInterrupt:
                    interrupted = True
                    record["reason"] = "INTERRUPTED"
                except subprocess.TimeoutExpired:
                    record["reason"] = "TIME_BUDGET"
                except (OSError, ValueError, TypeError, KeyError) as error:
                    code = str(error)
                    record["reason"] = (
                        code
                        if code
                        in {
                            "INPUT_CHANGED",
                            "CODE_CHANGED",
                            "TIME_BUDGET",
                            "INTERRUPTED",
                            "INVALID_STUDY_RESULT",
                            "INVALID_STUDY_ARTIFACT",
                        }
                        else "STUDY_INPUT_OR_CHILD_UNAVAILABLE"
                    )
            records.append(record)
            write_json(output / "study-results.json", aggregate())
    for data in plan["inputs"]:
        try:
            verify_manifest(Path(data["manifest"]))
            if digest(Path(data["manifest"])) != data["manifest_sha256"]:
                raise ValueError
        except (ValueError, OSError, KeyError, TypeError):
            invalidate_market(records, data["market"], "INPUT_CHANGED_POST_RUN")
    if not _source_matches(
        Path(__file__).resolve().parents[3], plan["code_identity"]["source_sha256"]
    ):
        for market in {r["market"] for r in records}:
            invalidate_market(records, market, "CODE_CHANGED")
    pair_records(records)
    result = aggregate()
    write_json(output / "study-results.json", result)
    return result
