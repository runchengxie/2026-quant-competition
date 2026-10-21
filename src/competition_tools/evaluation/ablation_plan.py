"""Freeze a bounded, separately versioned policy experiment."""

import copy
from pathlib import Path
from competition_tools.datasets.storage import write_json
from competition_tools.team.paths import validate_external
from .study_identity import canonical_hash, tree_hash
from .study_inputs import load_study_input
from .study_plan import COSTS, PARAMETERS, validate_job, plan_hash
from .ablation_catalog import (
    validate_ablation_spec,
    variant_spec,
    load_origin_evidence,
    CATALOG_SHA256,
)
from .ablation_source import snapshot_source

BUDGET = {"jobs": 768, "seconds": 3600, "batch_jobs": 384}
EXTRA = {
    "variant_id",
    "variant_parameters",
    "evidence_role",
    "origin",
    "catalog_sha256",
}
JOB_KEYS = (
    set(
        "schema market project status manifest manifest_sha256 input_files input_slice products benchmark quote_currency strategy parameters fee_bps fold dates accounting_model execution_assumption independent_fold_start max_positions max_gross_exposure signal_lag_periods expected_leaf_sha256 accepted_research job_id code_commit plan_sha256".split()
    )
    | EXTRA
)
ID_KEYS = tuple(sorted(JOB_KEYS - {"job_id", "plan_sha256"}))


def job_hash(job):
    return canonical_hash({k: job[k] for k in ID_KEYS})


def ablation_plan_hash(plan: dict) -> str:
    return plan_hash(plan)


def validate_ablation_job(job: dict) -> None:
    try:
        if job["status"] == "blocked":
            if (
                set(job)
                != {
                    "schema",
                    "job_id",
                    "market",
                    "status",
                    "reason",
                    "accepted_research",
                    "plan_sha256",
                }
                or job["schema"] != "competition.daily_study_job.v2"
            ):
                raise ValueError
            validate_job(job)
            return
        if (
            set(job) != JOB_KEYS
            or job["schema"] != "competition.daily_study_job.v2"
            or job["catalog_sha256"] != CATALOG_SHA256
        ):
            raise ValueError
        if any(
            type(job[k]) is not int
            for k in [
                "fee_bps",
                "max_positions",
                "max_gross_exposure",
                "signal_lag_periods",
            ]
        ):
            raise ValueError
        if job["max_gross_exposure"] != 1 or job["max_positions"] != (
            20 if job["market"] == "crypto" else 10
        ):
            raise ValueError
        if any(
            type(job["fold"][k]) is not int
            for k in ["warmup_periods", "scoring_periods"]
        ):
            raise ValueError
        policy = variant_spec(job["market"], job["strategy"], job["variant_id"])
        if (
            any(canonical_hash(job[k]) != canonical_hash(v) for k, v in policy.items())
            or job_hash(job) != job["job_id"]
        ):
            raise ValueError
        if set(job["origin"]) != {
            "probe_protocol_sha256",
            "diagnostic_protocol_sha256",
            "evidence_manifest_sha256",
            "stage",
            "retrospective",
            "accepted_research",
        }:
            raise ValueError
        if (
            job["origin"]["stage"] != "retrospective"
            or job["origin"]["retrospective"] is not True
            or job["origin"]["accepted_research"] is not False
        ):
            raise ValueError
        if any(
            len(job["origin"][k]) != 64
            or any(c not in "0123456789abcdef" for c in job["origin"][k])
            for k in (
                "probe_protocol_sha256",
                "diagnostic_protocol_sha256",
                "evidence_manifest_sha256",
            )
        ):
            raise ValueError
        if canonical_hash(job["parameters"]) != canonical_hash(
            PARAMETERS[job["strategy"]]
        ):
            raise ValueError
        legacy = {k: v for k, v in job.items() if k not in EXTRA}
        legacy["schema"] = "competition.daily_study_job.v1"
        validate_job(legacy)
        canonical_hash(job)
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("INVALID_ABLATION_JOB") from None


def freeze_ablation(spec: dict, output_root: Path, *, code_identity: dict) -> dict:
    spec = validate_ablation_spec(spec)
    origin = load_origin_evidence(spec["origin"])
    out = validate_external(output_root)
    if out.exists():
        raise FileExistsError("STUDY_OUTPUT_EXISTS")
    inputs = []
    jobs = []
    seen = set()
    root = Path(code_identity["source_root"])

    def blocked(market, reason):
        value = {
            "schema": "competition.daily_study_job.v2",
            "market": market,
            "status": "blocked",
            "reason": reason,
            "accepted_research": False,
        }
        value["job_id"] = canonical_hash(value)
        jobs.append(value)

    for name in spec["manifests"]:
        try:
            data = load_study_input(Path(name))
        except (ValueError, OSError, KeyError, TypeError):
            blocked("unknown", "INVALID_STUDY_INPUT")
            continue
        market = data["market"]
        if market in seen or market not in spec["variants"]:
            raise ValueError("DUPLICATE_OR_UNSELECTED_MARKET")
        seen.add(market)
        inputs.append(data)
        dates = data["dates"]
        score = 90 if market == "crypto" else 63
        if len(dates) < 252 + score:
            blocked(market, "INSUFFICIENT_HISTORY")
            continue
        project = "crypto-mm" if market == "crypto" else "equity-lab"
        leaf_hash = tree_hash(root / "research" / project / "src")
        for first in range(252, len(dates) - score + 1, score):
            fold = {
                "warmup_start": dates[first - 252],
                "start": dates[first],
                "end": dates[first + score - 1],
                "warmup_periods": 252,
                "scoring_periods": score,
            }
            for item in spec["variants"][market]:
                strategy = item["strategy"]
                for fee in COSTS[market]:
                    j = {
                        "schema": "competition.daily_study_job.v2",
                        "market": market,
                        "project": project,
                        "status": "planned",
                        "manifest": data["manifest"],
                        "manifest_sha256": data["manifest_sha256"],
                        "input_files": data["input_files"],
                        "input_slice": data["slice"],
                        "products": [data["benchmark"]]
                        if strategy == "benchmark_buy_hold"
                        else data["products"],
                        "benchmark": data["benchmark"],
                        "quote_currency": data["quote_currency"],
                        "strategy": strategy,
                        "parameters": copy.deepcopy(PARAMETERS[strategy]),
                        "fee_bps": fee,
                        "fold": fold,
                        "dates": dates[first - 252 : first + score],
                        "accounting_model": "self_financing_daily.v1",
                        "execution_assumption": "lagged_close_proxy",
                        "independent_fold_start": True,
                        "max_positions": 20 if market == "crypto" else 10,
                        "max_gross_exposure": 1,
                        "signal_lag_periods": 1,
                        "expected_leaf_sha256": leaf_hash,
                        "accepted_research": False,
                        "code_commit": code_identity["commit"],
                        **variant_spec(market, strategy, item["variant_id"]),
                        "catalog_sha256": CATALOG_SHA256,
                        "origin": origin,
                    }
                    j["job_id"] = job_hash(j)
                    jobs.append(j)
    for market in COSTS.keys() - seen:
        blocked(market, "MARKET_INPUT_UNAVAILABLE")
    jobs.sort(key=lambda j: j["job_id"])
    if len(jobs) > BUDGET["jobs"] or len({j["job_id"] for j in jobs}) != len(jobs):
        raise ValueError("ABLATION_JOB_BUDGET_OR_DUPLICATE")
    receipt = snapshot_source(root, out / "retained")
    if any(receipt[k] != code_identity[k] for k in ["commit", "source_sha256"]):
        raise ValueError("SOURCE_SNAPSHOT_MISMATCH")
    identity = {k: receipt[k] for k in ["commit", "source_root", "source_sha256"]}
    plan = {
        "schema": "competition.study_plan.v2",
        "code_identity": identity,
        "source_receipt": receipt,
        "costs": copy.deepcopy(COSTS),
        "inputs": inputs,
        "jobs": jobs,
        "retrospective": True,
        "selection": "fixed_current_from_2023",
        "budget": copy.deepcopy(BUDGET),
        "accepted_research": False,
        "origin": origin,
        "catalog_sha256": CATALOG_SHA256,
    }
    plan["plan_sha256"] = ablation_plan_hash(plan)
    (out / "jobs").mkdir()
    for j in jobs:
        j["plan_sha256"] = plan["plan_sha256"]
        validate_ablation_job(j)
        write_json(out / "jobs" / (j["job_id"] + ".json"), j)
    write_json(out / "plan.json", plan)
    return plan
