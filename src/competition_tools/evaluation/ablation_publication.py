"""Reconstruct separate reviewed ablation aggregates from verified private artifacts."""

import argparse
import copy
import json
import math
from datetime import datetime
from pathlib import Path
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest, write_json
from .study_inputs import load_study_input
from .study_identity import canonical_hash
from .study_publication import (
    POOLS,
    REASONS,
    METRICS,
    BLOCKERS,
    RESULT_KEYS,
    METHOD_KEYS,
    validate_public_study,
)
from .ablation_catalog import CATALOG_SHA256, variant_spec
from .ablation_plan import validate_ablation_job, ablation_plan_hash
from .ablation_runner import verify_plan, verify_ablation_result, methods_for, PAIRED

POLICY_KEYS = {"variant_id", "variant_parameters", "evidence_role"}
ROW_KEYS = RESULT_KEYS | POLICY_KEYS | {"baseline_job_id", *PAIRED}
TOP_KEYS = set(
    "schema as_of code_commit plan_sha256 catalog_sha256 origin methods coverage results blockers".split()
)
ORIGIN_KEYS = set(
    "probe_protocol_sha256 diagnostic_protocol_sha256 evidence_manifest_sha256 stage retrospective accepted_research".split()
)


def pair_public_rows(rows):
    def key(r):
        return (r["market"], r["cost_bps"], r["start"], r["end"], r["quote_currency"])

    complete = [r for r in rows if r["status"] == "completed"]
    baselines = {
        (key(r), r["strategy"]): r for r in complete if r["variant_id"] == "baseline"
    }
    for r in rows:
        r.update(
            baseline_job_id=None,
            benchmark_return=None,
            excess_return=None,
            **{k: None for k in PAIRED},
        )
    metric_map = {
        "paired_net_change": "net_return",
        "paired_drawdown_change": "max_drawdown",
        "paired_turnover_change": "mean_daily_oneway_turnover_proxy",
        "paired_exposure_change": "mean_exposure",
    }
    for r in complete:
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
                **{name: r[k] - base[k] for name, k in metric_map.items()},
            )
        if benchmark is not None:
            r.update(
                benchmark_return=benchmark["net_return"],
                excess_return=r["net_return"] - benchmark["net_return"],
            )


def _same(actual, expected):
    if expected is None:
        return actual is None
    if type(expected) in (int, float):
        return (
            type(actual) in (int, float)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10)
        )
    return canonical_hash(actual) == canonical_hash(expected)


def validate_public_ablation(value: dict) -> dict:
    try:
        if (
            set(value) != TOP_KEYS
            or value["schema"] != "competition.public_ablation.v1"
            or value["catalog_sha256"] != CATALOG_SHA256
            or len(value["results"]) > 768
        ):
            raise ValueError
        origin = value["origin"]
        if (
            set(origin) != ORIGIN_KEYS
            or origin["stage"] != "retrospective"
            or origin["retrospective"] is not True
            or origin["accepted_research"] is not False
        ):
            raise ValueError
        if any(
            not isinstance(origin[k], str)
            or len(origin[k]) != 64
            or any(c not in "0123456789abcdef" for c in origin[k])
            for k in ORIGIN_KEYS
            if k.endswith("sha256")
        ):
            raise ValueError
        methods = {}
        legacy_methods = {}
        for m in value["methods"]:
            if set(m) != METHOD_KEYS | POLICY_KEYS:
                raise ValueError
            market = {"us": "US", "hk": "HK", "crypto": "crypto"}.get(
                m["method_id"].split(".")[0]
            )
            job = {
                "market": market,
                "strategy": m["strategy"],
                "fold": {"scoring_periods": 90 if market == "crypto" else 63},
                **variant_spec(market, m["strategy"], m["variant_id"]),
            }
            if (
                canonical_hash(m) != canonical_hash(methods_for(job))
                or m["method_id"] in methods
            ):
                raise ValueError
            methods[m["method_id"]] = m
            legacy = {k: v for k, v in m.items() if k not in POLICY_KEYS}
            legacy["method_id"] = (
                market.lower() + "." + m["strategy"] + ".self_financing_daily.v1"
            )
            hold = m["strategy"] in {"buy_hold", "benchmark_buy_hold"} or (
                market == "crypto" and m["strategy"] == "equal_weight"
            )
            legacy["rebalance"] = "buy_hold" if hold else "daily_target_weights"
            legacy_methods[legacy["method_id"]] = legacy
        ids = set()
        semantics = set()
        legacy_rows = []
        for r in value["results"]:
            if set(r) != ROW_KEYS or r["job_id"] in ids:
                raise ValueError
            ids.add(r["job_id"])
            if r["strategy"] is not None:
                if type(r["cost_bps"]) is not int:
                    raise ValueError
                if r["status"] == "completed" and any(
                    type(r[k]) is not int for k in ["sessions", "flat_days_proxy"]
                ):
                    raise ValueError
                policy = variant_spec(r["market"], r["strategy"], r["variant_id"])
                if any(
                    canonical_hash(r[k]) != canonical_hash(v) for k, v in policy.items()
                ):
                    raise ValueError
                semantic = (
                    r["market"],
                    r["strategy"],
                    r["variant_id"],
                    r["cost_bps"],
                    r["start"],
                    r["end"],
                )
                if semantic in semantics:
                    raise ValueError
                semantics.add(semantic)
            elif any(r[k] is not None for k in POLICY_KEYS):
                raise ValueError
            legacy = {k: v for k, v in r.items() if k in RESULT_KEYS}
            if r["status"] == "completed":
                expected_id = (
                    r["market"].lower()
                    + "."
                    + r["strategy"]
                    + "."
                    + r["variant_id"]
                    + ".self_financing_daily.v1"
                )
                if r["method_id"] != expected_id or r["method_id"] not in methods:
                    raise ValueError
                legacy["method_id"] = (
                    r["market"].lower()
                    + "."
                    + r["strategy"]
                    + ".self_financing_daily.v1"
                )
            legacy_rows.append(legacy)
        # Reuse only established scalar/coverage checks, preserving the old cap and API.
        # This internal validation view is never persisted as legacy research facts.
        for first in range(0, max(1, len(legacy_rows)), 384):
            validate_public_study(
                {
                    **{
                        k: value[k]
                        for k in [
                            "as_of",
                            "code_commit",
                            "plan_sha256",
                            "coverage",
                            "blockers",
                        ]
                    },
                    "schema": "competition.public_study.v1",
                    "methods": list(legacy_methods.values()),
                    "results": legacy_rows[first : first + 384],
                }
            )
        expected = copy.deepcopy(value["results"])
        pair_public_rows(expected)
        for r, e in zip(value["results"], expected):
            if any(
                not _same(r[k], e[k])
                for k in [
                    "baseline_job_id",
                    "benchmark_return",
                    "excess_return",
                    *PAIRED,
                ]
            ):
                raise ValueError
        canonical_hash(value)
    except (ValueError, KeyError, TypeError, AttributeError, IndexError):
        raise ValueError("INVALID_PUBLIC_ABLATION") from None
    return value


def project_ablation(aggregate: dict) -> dict:
    if (
        aggregate.get("schema") != "competition.study_results.v2"
        or aggregate.get("accepted_research") is not False
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    plan_path = safe_path(Path(aggregate["plan_path"]))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        plan.get("schema") != "competition.study_plan.v2"
        or ablation_plan_hash(plan) != aggregate["plan_sha256"]
        or plan["plan_sha256"] != aggregate["plan_sha256"]
        or plan["code_identity"]["commit"] != aggregate["code_commit"]
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    verify_plan(plan_path)
    observed = datetime.fromisoformat(aggregate["observed_at"])
    if observed.tzinfo is None:
        raise ValueError("INVALID_STUDY_TIMESTAMP")
    planned = {j["job_id"]: j for j in plan["jobs"]}
    if (
        len(planned) != len(plan["jobs"])
        or len(planned) > 768
        or {r["job_id"] for r in aggregate["jobs"]} != set(planned)
        or len(aggregate["jobs"]) != len(planned)
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    coverage = []
    for data in plan["inputs"]:
        current = load_study_input(Path(data["manifest"]))
        if current != data or not set(data["products"]) <= POOLS[data["market"]]:
            raise ValueError("UNREVIEWED_STUDY_INPUT")
        coverage.append(
            dict(
                market=data["market"],
                source="binance_spot" if data["market"] == "crypto" else "ibkr_daily",
                status=data["parent_status"],
                products=data["products"],
                benchmark=data["benchmark"],
                quote_currency=data["quote_currency"],
                start=data["dates"][0],
                end=data["dates"][-1],
                rows=len(data["dates"])
                * (len(data["products"]) + (data["market"] != "crypto")),
                universe_status="fixed_current",
            )
        )
    results = []
    methods = {}
    for record in aggregate["jobs"]:
        job = planned[record["job_id"]]
        validate_ablation_job(job)
        if (
            json.loads(
                (plan_path.parent / "jobs" / (job["job_id"] + ".json")).read_text(
                    encoding="utf-8"
                )
            )
            != job
            or job.get("plan_sha256") != plan["plan_sha256"]
        ):
            raise ValueError("FROZEN_JOB_CHANGED")
        market = job["market"]
        if market not in POOLS and market != "unknown":
            raise ValueError("UNREVIEWED_STUDY_MARKET")
        if record["market"] != market or record["status"] not in {
            "completed",
            "blocked",
            "failed",
        }:
            raise ValueError("INVALID_STUDY_AGGREGATE")
        planned_job = job["status"] == "planned"
        if planned_job and (
            not set(job["products"]) <= POOLS[market]
            or job["benchmark"]
            != {"US": "SPY", "HK": "2800", "crypto": "equal_weight"}[market]
        ):
            raise ValueError("UNREVIEWED_STUDY_PRODUCTS")
        row = dict(
            job_id=job["job_id"],
            market=market,
            status=record["status"],
            reason_code=record["reason"],
            strategy=job.get("strategy"),
            method_id=None,
            accounting_model=job.get("accounting_model"),
            fold=job.get("fold"),
            start=job.get("fold", {}).get("start"),
            end=job.get("fold", {}).get("end"),
            products=job.get("products", []),
            benchmark=job.get("benchmark"),
            cost_bps=job.get("fee_bps"),
            quote_currency=job.get("quote_currency"),
            periods_per_year=(365 if market == "crypto" else 252)
            if planned_job
            else None,
            plan_sha256=plan["plan_sha256"],
            result_sha256=None,
            eligibility_basis="daily_model_proxy",
        )
        row.update({k: None for k in METRICS})
        row.update({k: job.get(k) for k in POLICY_KEYS})
        if record["status"] == "completed":
            if not planned_job or record["reason"] is not None:
                raise ValueError("FORGED_STUDY_COMPLETION")
            path = safe_path(Path(record["result_path"]))
            expected = safe_path(
                plan_path.parent / "run" / job["job_id"] / "result.json"
            )
            if path != expected or digest(path) != record["result_sha256"]:
                raise ValueError("STUDY_RESULT_CHANGED")
            result, _ = verify_ablation_result(job, path.parent)
            if result["metrics"] != record["metrics"]:
                raise ValueError("STUDY_METRICS_CHANGED")
            m = result["metrics"]
            method = result["methods"]
            methods[method["method_id"]] = method
            row.update(
                {
                    k: m[k]
                    for k in (
                        "net_return",
                        "gross_return",
                        "sharpe",
                        "volatility",
                        "max_drawdown",
                        "turnover",
                        "mean_exposure",
                        "cost_drag",
                    )
                }
            )
            row.update(
                method_id=method["method_id"],
                sessions=m["periods"],
                result_sha256=digest(path),
                mean_daily_position_proxy=m["mean_exposure"],
                mean_daily_oneway_turnover_proxy=m["mean_daily_turnover"],
                flat_days_proxy=m["flat_days"],
            )
        elif record["reason"] not in REASONS or record["metrics"] is not None:
            raise ValueError("INVALID_STUDY_BLOCKER")
        results.append(row)
    pair_public_rows(results)
    return validate_public_ablation(
        dict(
            schema="competition.public_ablation.v1",
            as_of=observed.date().isoformat(),
            code_commit=aggregate["code_commit"],
            plan_sha256=plan["plan_sha256"],
            catalog_sha256=plan["catalog_sha256"],
            origin=plan["origin"],
            methods=sorted(methods.values(), key=lambda m: m["method_id"]),
            coverage=coverage,
            results=results,
            blockers=BLOCKERS,
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aggregate", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    value = project_ablation(
        json.loads(safe_path(a.aggregate).read_text(encoding="utf-8"))
    )
    destination = safe_path(a.output)
    if destination.exists():
        raise ValueError("PUBLIC_ABLATION_OUTPUT_EXISTS")
    write_json(destination, value)


if __name__ == "__main__":
    main()
