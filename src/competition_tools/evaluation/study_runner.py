"""Dispatch frozen jobs to independent leaf CLIs and verify their artifacts."""

import json
import math
import subprocess
import time
from pathlib import Path, PurePosixPath

from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest, write_json, verify_manifest
from competition_tools.team.config import TeamConfig
from competition_tools.team.processes import interpreter, child_environment, run_child
from .study_identity import source_hash
from .study_plan import plan_hash, validate_job


def _verify_consumed(job):
    path = safe_path(Path(job["manifest"]))
    if digest(path) != job["manifest_sha256"]:
        raise ValueError("INPUT_CHANGED")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    known = {r["path"]: r for r in manifest["files"]}
    for record in job["input_files"]:
        relative = PurePosixPath(record["path"])
        if (
            len(relative.parts) != 2
            or relative.parts[0] != "normalized"
            or known.get(record["path"]) != record
        ):
            raise ValueError("INPUT_CHANGED")
        target = safe_path(path.parent / record["path"])
        if (
            target.stat().st_size != record["bytes"]
            or digest(target) != record["sha256"]
        ):
            raise ValueError("INPUT_CHANGED")


def _finite(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, list):
        return all(_finite(v) for v in value)
    return True


def _result(job, destination):
    path = safe_path(destination / "result.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    pairs = {
        "job_id": "job_id",
        "plan_sha256": "plan_sha256",
        "manifest_sha256": "manifest_sha256",
        "market": "market",
        "quote_currency": "quote_currency",
        "strategy": "strategy",
        "fee_bps": "fee_bps",
        "products": "products",
    }
    if (
        not isinstance(value, dict)
        or value.get("schema") != "competition.daily_study_result.v1"
        or not _finite(value)
        or value.get("accepted_research") is not False
        or any(value.get(a) != job[b] for a, b in pairs.items())
        or value.get("code_sha256") != job["expected_leaf_sha256"]
        or value.get("start") != job["fold"]["start"]
        or value.get("end") != job["fold"]["end"]
        or value.get("metrics", {}).get("periods") != job["fold"]["scoring_periods"]
    ):
        raise ValueError("INVALID_STUDY_RESULT")
    for artifact in value["artifacts"]:
        relative = PurePosixPath(artifact["path"])
        if len(relative.parts) != 1 or relative.name != "periods.json":
            raise ValueError("INVALID_STUDY_ARTIFACT")
        target = safe_path(destination / relative)
        if (
            target.stat().st_size != artifact["bytes"]
            or digest(target) != artifact["sha256"]
        ):
            raise ValueError("INVALID_STUDY_ARTIFACT")
    if len(value["artifacts"]) != 1:
        raise ValueError("INVALID_STUDY_ARTIFACT")
    return value, path


def run_study(config: TeamConfig, plan_path: Path) -> dict:
    plan_path = safe_path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        plan.get("schema") != "competition.study_plan.v1"
        or plan.get("plan_sha256") != plan_hash(plan)
        or len(plan["jobs"]) > 384
    ):
        raise ValueError("INVALID_FROZEN_PLAN")
    for job in plan["jobs"]:
        validate_job(job)
        if job.get("plan_sha256") != plan["plan_sha256"]:
            raise ValueError("INVALID_FROZEN_PLAN")
        if (
            json.loads(
                safe_path(
                    plan_path.parent / "jobs" / (job["job_id"] + ".json")
                ).read_text(encoding="utf-8")
            )
            != job
        ):
            raise ValueError("FROZEN_JOB_CHANGED")
    output = safe_path(plan_path.parent / "run")
    output.mkdir(exist_ok=False)
    started, records, interrupted = time.monotonic(), [], False
    for job in plan["jobs"]:
        record = {
            "job_id": job["job_id"],
            "market": job["market"],
            "status": job["status"],
            "reason": job.get("reason"),
            "metrics": None,
            "result_path": None,
            "result_sha256": None,
            "benchmark_excess_return": None,
            "blockers": [],
        }
        if job["status"] == "planned":
            record["status"] = "blocked"
            remaining = 3600 - (time.monotonic() - started)
            try:
                if interrupted:
                    raise ValueError("INTERRUPTED")
                if remaining <= 0:
                    raise ValueError("TIME_BUDGET")
                if (
                    source_hash(Path(plan["code_identity"]["source_root"]))
                    != plan["code_identity"]["source_sha256"]
                ):
                    raise ValueError("CODE_CHANGED")
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
                remaining = 3600 - (time.monotonic() - started)
                if remaining <= 0:
                    raise ValueError("TIME_BUDGET")
                child = run_child(
                    command, environment=child_environment(config), timeout=remaining
                )
                logs = output / (job["job_id"] + ".log")
                logs.write_text(child.stdout + "\n" + child.stderr, encoding="utf-8")
                if child.returncode != 0:
                    record.update(status="failed", reason="STUDY_CHILD_FAILED")
                else:
                    result, result_path = _result(job, destination)
                    _verify_consumed(job)
                    if (
                        source_hash(Path(plan["code_identity"]["source_root"]))
                        != plan["code_identity"]["source_sha256"]
                    ):
                        raise ValueError("CODE_CHANGED")
                    record.update(
                        status="completed",
                        reason=None,
                        metrics=result["metrics"],
                        result_path=str(result_path),
                        result_sha256=digest(result_path),
                        strategy=job["strategy"],
                        fee_bps=job["fee_bps"],
                        fold=job["fold"],
                        quote_currency=job["quote_currency"],
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
        write_json(
            output / "study-results.json",
            {
                "schema": "competition.study_results.v1",
                "plan_sha256": plan["plan_sha256"],
                "code_commit": plan["code_identity"]["commit"],
                "jobs": records,
                "accepted_research": False,
            },
        )
    # Recheck full upstream provenance after the run, including files not directly
    # consumed by the leaf calculations. A changed parent invalidates its jobs.
    for data in plan["inputs"]:
        try:
            verify_manifest(Path(data["manifest"]))
            if digest(Path(data["manifest"])) != data["manifest_sha256"]:
                raise ValueError
        except (ValueError, OSError, KeyError, TypeError):
            for record in records:
                if (
                    record["market"] == data["market"]
                    and record["status"] == "completed"
                ):
                    record.update(
                        status="blocked", reason="INPUT_CHANGED_POST_RUN", metrics=None
                    )
    benchmarks = {
        (r["market"], r["fold"]["start"], r["fee_bps"]): r
        for r in records
        if r["status"] == "completed"
        and r["strategy"]
        == ("equal_weight" if r["market"] == "crypto" else "benchmark_buy_hold")
    }
    for record in records:
        if record["status"] == "completed":
            benchmark = benchmarks.get(
                (record["market"], record["fold"]["start"], record["fee_bps"])
            )
            if benchmark is None:
                record["blockers"].append("BENCHMARK_UNAVAILABLE")
            else:
                record["benchmark_excess_return"] = (
                    record["metrics"]["net_return"] - benchmark["metrics"]["net_return"]
                )
    result = {
        "schema": "competition.study_results.v1",
        "plan_sha256": plan["plan_sha256"],
        "code_commit": plan["code_identity"]["commit"],
        "jobs": records,
        "accepted_research": False,
    }
    write_json(output / "study-results.json", result)
    return result
