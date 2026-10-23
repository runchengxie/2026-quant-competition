"""Freeze the exact parent comparisons and committed independently runnable source."""

from datetime import datetime, timezone
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ..controls.contracts import read_json
from ..controls.source import snapshot_source
from ..controls.verification import (
    verify_plan as verify_parent,
    validate_results_index,
    verify_control_result,
)
from ..study_identity import canonical_hash, source_hash, tree_hash
from .catalog import CATALOG_SHA256, POOLS, diagnostic_grid
from .contracts import job_hash, validate_job, validate_spec


def plan_hash(value: dict) -> str:
    return canonical_hash(
        {
            k: (
                [{a: b for a, b in j.items() if a != "plan_sha256"} for j in v]
                if k == "jobs"
                else v
            )
            for k, v in value.items()
            if k != "plan_sha256"
        }
    )


def freeze_robustness(spec: dict, output: Path, *, code_identity: dict) -> dict:
    validate_spec(spec)
    paths = {k: safe_path(Path(spec[k])) for k in ("parent_plan", "parent_results")}
    if any(digest(p) != spec["expected_" + k + "_sha256"] for k, p in paths.items()):
        raise ValueError("ROBUSTNESS_PARENT_CHANGED")
    parent = verify_parent(paths["parent_plan"])
    index = validate_results_index(parent, read_json(paths["parent_results"]))
    source = Path(code_identity["source_root"])
    if source_hash(source) != code_identity["source_sha256"]:
        raise ValueError("ROBUSTNESS_SOURCE_CHANGED")
    lookup = {r["job_id"]: r for r in index["jobs"]}
    jobs = []
    for row in diagnostic_grid(parent["jobs"]):
        base = row["input_job"]
        prior = lookup[base["job_id"]]
        if prior["status"] != "completed":
            raise ValueError("ROBUSTNESS_BASELINE_NOT_COMPLETED")
        baseline = safe_path(paths["parent_results"].parent / prior["result_path"])
        verify_control_result(base, baseline)
        market = base["market"]
        job = dict(
            schema="competition.strategy_robustness_job.v1",
            **row,
            parent_result=str(baseline),
            parent_result_sha256=digest(baseline),
            market=market,
            products=POOLS[row["pool_id"]] if market == "US" else base["products"],
            expected_leaf_sha256=tree_hash(
                source / "research" / base["project"] / "src"
            ),
            catalog_sha256=CATALOG_SHA256,
            code_commit=code_identity["commit"],
            accepted_research=False,
        )
        job["job_id"] = job_hash(job)
        jobs.append(job)
    out = safe_path(output)
    out.mkdir(parents=True, exist_ok=False)
    snapshot = snapshot_source(source, out / "source-snapshot")
    value = dict(
        schema="competition.strategy_robustness_plan.v1",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        catalog_sha256=CATALOG_SHA256,
        source_snapshot=snapshot,
        code_identity=code_identity,
        budget=dict(
            US=dict(jobs=66, seconds=600),
            crypto=dict(jobs=48, seconds=600, capacity_checks=288),
        ),
        jobs=jobs,
    )
    value["plan_sha256"] = plan_hash(value)
    for job in jobs:
        job["plan_sha256"] = value["plan_sha256"]
        validate_job(job)
    if any(digest(p) != spec["expected_" + k + "_sha256"] for k, p in paths.items()):
        raise ValueError("ROBUSTNESS_PARENT_CHANGED")
    write_json(out / "plan.json", value)
    return value


def verify_plan(path: Path) -> dict:
    from ..ablation_source import verify_source_snapshot

    value = read_json(path)
    if (
        value.get("schema") != "competition.strategy_robustness_plan.v1"
        or value.get("plan_sha256") != plan_hash(value)
        or value.get("catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("INVALID_ROBUSTNESS_PLAN")
    validate_spec(value["spec"])
    receipt = verify_source_snapshot(value["source_snapshot"])
    if (
        receipt["source_sha256"] != value["code_identity"]["source_sha256"]
        or receipt["commit"] != value["code_identity"]["commit"]
    ):
        raise ValueError("ROBUSTNESS_SOURCE_CHANGED")
    parent = verify_parent(Path(value["spec"]["parent_plan"]))
    for field in ("parent_plan", "parent_results"):
        if (
            digest(safe_path(Path(value["spec"][field])))
            != value["spec"]["expected_" + field + "_sha256"]
        ):
            raise ValueError("ROBUSTNESS_PARENT_CHANGED")
    expected = {
        (r["input_job"]["job_id"], r["pool_id"], r["fee_bps"])
        for r in diagnostic_grid(parent["jobs"])
    }
    found = set()
    for job in value["jobs"]:
        validate_job(job)
        identity = (job["input_job"]["job_id"], job["pool_id"], job["fee_bps"])
        if (
            identity in found
            or identity not in expected
            or job["plan_sha256"] != value["plan_sha256"]
        ):
            raise ValueError("INVALID_ROBUSTNESS_GRID")
        found.add(identity)
        if (
            job["expected_leaf_sha256"]
            != tree_hash(
                Path(receipt["source_root"])
                / "research"
                / job["input_job"]["project"]
                / "src"
            )
            or digest(safe_path(Path(job["parent_result"])))
            != job["parent_result_sha256"]
        ):
            raise ValueError("ROBUSTNESS_SOURCE_OR_BASELINE_CHANGED")
    if found != expected or len(value["jobs"]) != 114:
        raise ValueError("INCOMPLETE_ROBUSTNESS_GRID")
    return value
