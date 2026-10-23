"""One cumulative clock, durable checkpoints and independent CLI verification."""

import math
import os
import subprocess
import time
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ...team.processes import child_environment, interpreter, run_child
from .contracts import read_json
from .verification import (
    verify_plan,
    verify_control_result as verify_control_result,
    validate_results_index,
)
from ..study_identity import canonical_hash

OWNER = "competition.strategy_controls_run.v1"


def batches(jobs):
    if len(jobs) > 512:
        raise ValueError("CONTROLS_JOB_BUDGET")
    return [jobs[i : i + 384] for i in range(0, len(jobs), 384)]


def remaining_seconds(start, *, spent=0, now=None):
    return 3600 - spent - ((time.monotonic() if now is None else now) - start)


def _files(root):
    return [
        {
            "path": p.relative_to(root).as_posix(),
            "sha256": digest(safe_path(p)),
            "bytes": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and p.relative_to(root).as_posix()
        not in {".lock", ".owner", "state.json", "state.sha256"}
    ]


def _record(job, *, reason="NOT_RUN"):
    return dict(
        job_id=job["job_id"],
        market=job["market"],
        arm_id=job["arm_id"],
        fee_bps=job["fee_bps"],
        status="blocked",
        reason=reason,
        metrics=None,
        result_path=None,
    )


def run_controls(config, plan_path: Path) -> dict:
    origin = time.monotonic()
    path = safe_path(plan_path)
    plan = verify_plan(path)
    root = safe_path(path.parent / "run")
    previous = None
    if root.exists():
        if not (root / ".owner").is_file() or (root / ".owner").read_text() != OWNER:
            raise ValueError("UNOWNED_CONTROLS_RUN")
        if (root / ".lock").exists():
            raise ValueError("CONTROLS_RUN_BUSY")
        if (
            not (root / "state.sha256").is_file()
            or digest(root / "state.json")
            != (root / "state.sha256").read_text().strip()
        ):
            raise ValueError("UNKNOWN_CONTROLS_SPEND")
        previous = read_json(root / "state.json")
        if (
            set(previous)
            != {
                "schema",
                "plan_sha256",
                "phase",
                "elapsed_seconds",
                "attempted_ids",
                "files",
            }
            or previous["schema"] != OWNER
            or previous["plan_sha256"] != plan["plan_sha256"]
            or previous["phase"] not in {"checkpoint", "terminal"}
            or previous["files"] != _files(root)
        ):
            raise ValueError("UNKNOWN_CONTROLS_SPEND_OR_CHANGED_RUN")
        if (
            type(previous["elapsed_seconds"]) not in (int, float)
            or not math.isfinite(previous["elapsed_seconds"])
            or previous["elapsed_seconds"] < 0
        ):
            raise ValueError("UNKNOWN_CONTROLS_SPEND")
        attempted_ids = previous["attempted_ids"]
        known_ids = {j["job_id"] for j in plan["jobs"]}
        if (
            not isinstance(attempted_ids, list)
            or any(not isinstance(j, str) or j not in known_ids for j in attempted_ids)
            or len(set(attempted_ids)) != len(attempted_ids)
            or (previous["phase"] == "terminal" and set(attempted_ids) != known_ids)
        ):
            raise ValueError("UNKNOWN_CONTROLS_SPEND")
        cached = validate_results_index(plan, read_json(root / "results.json"))
        if cached["elapsed_seconds"] > previous["elapsed_seconds"]:
            raise ValueError("UNKNOWN_CONTROLS_SPEND")
        for record in cached["jobs"]:
            if record["status"] == "completed":
                job = next(j for j in plan["jobs"] if j["job_id"] == record["job_id"])
                actual = verify_control_result(
                    job, safe_path(root / record["result_path"])
                )
                if canonical_hash(actual["metrics"]) != canonical_hash(
                    record["metrics"]
                ):
                    raise ValueError("CONTROLS_SUMMARY_CHANGED")
            if (record["reason"] != "NOT_RUN") != (record["job_id"] in attempted_ids):
                raise ValueError("UNKNOWN_CONTROLS_SPEND")
        if previous["phase"] == "terminal":
            return cached
    else:
        root.mkdir(parents=True, exist_ok=False)
        (root / ".owner").write_text(OWNER)
    fd = os.open(root / ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    spent = previous["elapsed_seconds"] if previous else 0
    attempted = set(previous["attempted_ids"]) if previous else set()
    records = (
        read_json(root / "results.json")["jobs"]
        if previous
        else [_record(j) for j in plan["jobs"]]
    )
    by_id = {r["job_id"]: r for r in records}
    phase = "checkpoint"

    def checkpoint():
        files = _files(root)
        state = dict(
            schema=OWNER,
            plan_sha256=plan["plan_sha256"],
            phase=phase,
            elapsed_seconds=spent + max(0, time.monotonic() - origin),
            attempted_ids=sorted(attempted),
            files=files,
        )
        write_json(root / "state.json", state)
        (root / "state.sha256").write_text(digest(root / "state.json"))
        return state

    def result_value():
        complete = all(r["status"] == "completed" for r in records)
        return dict(
            schema="competition.strategy_controls_results.v1",
            plan_sha256=plan["plan_sha256"],
            status="completed"
            if complete and remaining_seconds(origin, spent=spent) > 0
            else "partial",
            elapsed_seconds=spent + max(0, time.monotonic() - origin),
            jobs=records,
        )

    try:
        write_json(root / "results.json", result_value())
        checkpoint()
        environment = child_environment(config)
        for name in list(environment):
            if name.upper().endswith(("API_KEY", "TOKEN", "PASSWORD")):
                environment.pop(name)
        batch_number = len(list(root.glob("batch-*.json")))
        interrupted = False
        for market in ("US", "crypto"):
            pending = [
                j
                for j in plan["jobs"]
                if j["market"] == market and j["job_id"] not in attempted
            ]
            for group in batches(pending):
                left = remaining_seconds(origin, spent=spent)
                if left <= 0:
                    for job in group:
                        by_id[job["job_id"]].update(reason="TIME_BUDGET")
                        attempted.add(job["job_id"])
                    continue
                batch_path = root / f"batch-{batch_number:04}.json"
                output = root / f"batch-{batch_number:04}"
                batch_number += 1
                write_json(
                    batch_path,
                    dict(
                        schema="competition.strategy_controls_batch.v1",
                        plan_sha256=plan["plan_sha256"],
                        market=market,
                        jobs=group,
                    ),
                )
                phase = "running_child"
                checkpoint()
                # Saving/checking a large checkpoint consumes the same budget.
                left = remaining_seconds(origin, spent=spent)
                if left <= 0:
                    phase = "checkpoint"
                    for job in group:
                        by_id[job["job_id"]].update(reason="TIME_BUDGET")
                        attempted.add(job["job_id"])
                    continue
                module = (
                    "equity_lab.study.controls_cli"
                    if market == "US"
                    else "crypto_mm.daily.controls_cli"
                )
                try:
                    run_child(
                        [
                            str(interpreter(config, group[0]["project"])),
                            "-m",
                            module,
                            "--jobs",
                            str(batch_path),
                            "--output-root",
                            str(output),
                        ],
                        environment=environment,
                        timeout=max(1, min(3600, left)),
                    )
                except KeyboardInterrupt:
                    interrupted = True
                except (OSError, TimeoutError):
                    pass
                except subprocess.TimeoutExpired:
                    pass
                for job in group:
                    record = by_id[job["job_id"]]
                    attempted.add(job["job_id"])
                    result_path = output / job["job_id"] / "result.json"
                    try:
                        value = verify_control_result(job, result_path)
                        record.update(
                            status="completed",
                            reason=None,
                            metrics=value["metrics"],
                            result_path=result_path.relative_to(root).as_posix(),
                        )
                    except (ValueError, OSError, KeyError, TypeError, IndexError):
                        record.update(reason="LEAF_JOB_FAILED_OR_INVALID")
                phase = "checkpoint"
                write_json(root / "results.json", result_value())
                checkpoint()
                if interrupted:
                    break
            if interrupted:
                break
        # Recheck every input/source after I/O before finalizing accepted results.
        verify_plan(path)
        phase = "terminal" if len(attempted) == len(plan["jobs"]) else "checkpoint"
        value = result_value()
        write_json(root / "results.json", value)
        state = checkpoint()
        if state["elapsed_seconds"] >= 3600 and value["status"] == "completed":
            value["status"] = "partial"
            write_json(root / "results.json", value)
            checkpoint()
        return value
    finally:
        os.close(fd)
        (root / ".lock").unlink()
