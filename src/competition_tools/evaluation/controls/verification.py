"""Verify frozen controls, source retention and independently reported economics."""

import math
from pathlib import Path, PurePosixPath

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest
from ..ablation_source import verify_source_snapshot
from ..ablation_runner import _verify_period_metrics
from ..study_identity import canonical_hash, tree_hash
from ..study_inputs import load_study_input
from ..study_runner import _verify_consumed
from .catalog import CATALOG_SHA256
from .contracts import read_json, validate_job, validate_spec, plan_hash

RESULT_KEYS = set(
    "schema status job_id plan_sha256 manifest_sha256 expected_leaf_sha256 code_commit market arm_id fee_bps quote_currency metrics diagnostics artifacts accepted_research issue_codes".split()
)


def validate_results_index(plan: dict, value: dict) -> dict:
    """Validate the full denominator before trusting any cached summaries."""
    try:
        if (
            set(value) != {"schema", "plan_sha256", "status", "elapsed_seconds", "jobs"}
            or value["schema"] != "competition.strategy_controls_results.v1"
            or value["plan_sha256"] != plan["plan_sha256"]
            or value["status"] not in {"completed", "partial"}
            or type(value["elapsed_seconds"]) not in (int, float)
            or not math.isfinite(value["elapsed_seconds"])
            or value["elapsed_seconds"] < 0
            or not isinstance(value["jobs"], list)
            or len(value["jobs"]) != len(plan["jobs"])
        ):
            raise ValueError
        lookup = {j["job_id"]: j for j in plan["jobs"]}
        seen = set()
        for row in value["jobs"]:
            if set(row) != {
                "job_id",
                "market",
                "arm_id",
                "fee_bps",
                "status",
                "reason",
                "metrics",
                "result_path",
            }:
                raise ValueError
            job = lookup[row["job_id"]]
            if row["job_id"] in seen:
                raise ValueError
            seen.add(row["job_id"])
            if any(
                canonical_hash(row[k]) != canonical_hash(job[k])
                for k in ("market", "arm_id", "fee_bps")
            ):
                raise ValueError
            if row["status"] == "blocked":
                if (
                    row["metrics"] is not None
                    or row["result_path"] is not None
                    or row["reason"]
                    not in {"NOT_RUN", "TIME_BUDGET", "LEAF_JOB_FAILED_OR_INVALID"}
                ):
                    raise ValueError
            elif row["status"] == "completed":
                relative = PurePosixPath(row["result_path"])
                if (
                    not isinstance(row["metrics"], dict)
                    or row["reason"] is not None
                    or len(relative.parts) != 3
                    or not relative.parts[0].startswith("batch-")
                    or relative.parts[1:] != (job["job_id"], "result.json")
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or "\\" in row["result_path"]
                    or ":" in row["result_path"]
                ):
                    raise ValueError
            else:
                raise ValueError
        if value["status"] == "completed" and (
            any(r["status"] != "completed" for r in value["jobs"])
            or value["elapsed_seconds"] >= 3600
        ):
            raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError("INVALID_CONTROLS_RESULTS") from None
    return value


def verify_plan(path: Path) -> dict:
    value = read_json(path)
    expected = set(
        "schema frozen_at spec code_commit source_sha256 source_snapshot scientific_source_files catalog_sha256 inputs jobs plan_sha256".split()
    )
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value["schema"] != "competition.strategy_controls_plan.v1"
        or value["plan_sha256"] != plan_hash(value)
        or value["catalog_sha256"] != CATALOG_SHA256
    ):
        raise ValueError("INVALID_CONTROLS_PLAN")
    validate_spec(value["spec"])
    receipt = verify_source_snapshot(value["source_snapshot"])
    if (
        receipt["commit"] != value["code_commit"]
        or receipt["source_sha256"] != value["source_sha256"]
    ):
        raise ValueError("CONTROLS_SOURCE_CHANGED")
    source = safe_path(Path(receipt["source_root"]))
    records = [
        {"path": p.relative_to(source).as_posix(), "sha256": digest(p)}
        for directory in ("src", "research/equity-lab/src", "research/crypto-mm/src")
        for p in sorted((source / directory).rglob("*.py"))
    ]
    if records != value["scientific_source_files"]:
        raise ValueError("CONTROLS_SOURCE_CHANGED")
    data = {}
    leaf = {}
    expected_ids = set()
    for market, name in value["spec"]["manifests"].items():
        data[market] = load_study_input(safe_path(Path(name)))
        if (
            canonical_hash(data[market]) != canonical_hash(value["inputs"][market])
            or data[market]["manifest_sha256"]
            != value["spec"]["expected_input_hashes"][market]
        ):
            raise ValueError("CONTROLS_INPUT_CHANGED")
        leaf[market] = tree_hash(
            source
            / "research"
            / ("equity-lab" if market == "US" else "crypto-mm")
            / "src"
        )
        score = 63 if market == "US" else 90
        for first in range(252, len(data[market]["dates"]) - score + 1, score):
            for arm in value["spec"]["arms"][market]:
                for fee in value["spec"]["costs"][market]:
                    expected_ids.add((market, arm, fee, data[market]["dates"][first]))
    if not 1 <= len(value["jobs"]) <= 512 or len(value["jobs"]) != len(expected_ids):
        raise ValueError("CONTROLS_JOB_BUDGET_OR_GRID")
    found = set()
    for job in value["jobs"]:
        validate_job(job)
        market = job["market"]
        identity = (market, job["arm_id"], job["fee_bps"], job["fold"]["start"])
        if identity in found or identity not in expected_ids:
            raise ValueError("INVALID_CONTROLS_GRID")
        found.add(identity)
        if (
            job["plan_sha256"] != value["plan_sha256"]
            or job["code_commit"] != value["code_commit"]
            or job["expected_leaf_sha256"] != leaf[market]
        ):
            raise ValueError("CONTROLS_IDENTITY_MISMATCH")
        for key, data_key in (
            ("manifest", "manifest"),
            ("manifest_sha256", "manifest_sha256"),
            ("products", "products"),
            ("benchmark", "benchmark"),
            ("quote_currency", "quote_currency"),
            ("input_files", "input_files"),
            ("input_slice", "slice"),
        ):
            if canonical_hash(job[key]) != canonical_hash(data[market][data_key]):
                raise ValueError("CONTROLS_INPUT_CHANGED")
        first = data[market]["dates"].index(job["fold"]["start"])
        if (
            job["dates"]
            != data[market]["dates"][
                first - 252 : first + job["fold"]["scoring_periods"]
            ]
        ):
            raise ValueError("INVALID_CONTROLS_GRID")
        _verify_consumed(job)
    if found != expected_ids:
        raise ValueError("INVALID_CONTROLS_GRID")
    return value


def verify_control_result(job: dict, result_path: Path) -> dict:
    validate_job(job)
    path = safe_path(result_path)
    before = digest(path)
    value = read_json(path)
    if (
        not isinstance(value, dict)
        or set(value) != RESULT_KEYS
        or value["schema"] != "competition.strategy_controls_result.v1"
        or value["status"] != "completed"
        or value["accepted_research"] is not False
        or value["issue_codes"] != []
    ):
        raise ValueError("INVALID_CONTROLS_RESULT")
    for key in "job_id plan_sha256 manifest_sha256 expected_leaf_sha256 code_commit market arm_id fee_bps quote_currency".split():
        if canonical_hash(value[key]) != canonical_hash(job[key]):
            raise ValueError("CONTROLS_RESULT_IDENTITY_MISMATCH")
    artifacts = value["artifacts"]
    if (
        not isinstance(artifacts, list)
        or len(artifacts) != 1
        or set(artifacts[0]) != {"path", "bytes", "sha256"}
        or artifacts[0]["path"] != "periods.json"
        or type(artifacts[0]["bytes"]) is not int
    ):
        raise ValueError("INVALID_CONTROLS_PERIODS")
    periods_path = safe_path(path.parent / "periods.json")
    if (
        periods_path.stat().st_size != artifacts[0]["bytes"]
        or digest(periods_path) != artifacts[0]["sha256"]
    ):
        raise ValueError("CONTROLS_PERIODS_CHANGED")
    periods = read_json(periods_path)
    if (
        set(periods) != {"schema", "job_id", "plan_sha256", "net", "gross"}
        or periods["schema"] != "competition.strategy_controls_periods.v1"
        or periods["job_id"] != job["job_id"]
        or periods["plan_sha256"] != job["plan_sha256"]
    ):
        raise ValueError("INVALID_CONTROLS_PERIODS")
    # Reuse only the existing root arithmetic validator, not its v2 artifacts.
    internal = {k: v for k, v in periods.items() if k != "plan_sha256"}
    internal["schema"] = "competition.daily_study_periods.v2"
    _verify_period_metrics(job, value, internal)
    if digest(path) != before or digest(periods_path) != artifacts[0]["sha256"]:
        raise ValueError("CONTROLS_RESULT_CHANGED")
    return value
