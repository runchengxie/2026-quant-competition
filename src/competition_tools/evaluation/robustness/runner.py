"""One irreversible reservation per fixed grid and market, including failures."""

import subprocess
import time
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ...team.processes import child_environment, interpreter, run_child
from ..controls.contracts import read_json
from ..study_identity import canonical_hash
from .catalog import CATALOG_SHA256
from .plan import verify_plan
from .verification import verify_robustness_result


def reserve_market(parent_plan: Path, parent_hash: str, market: str) -> Path:
    parent = safe_path(parent_plan)
    if market not in {"US", "crypto"} or digest(parent) != parent_hash:
        raise ValueError("ROBUSTNESS_RESERVATION_PARENT_MISMATCH")
    owner = next((p.parent for p in parent.parents if p.name == "task-results"), parent.parent.parent)
    identity = canonical_hash(dict(parent=parent_hash, catalog=CATALOG_SHA256, market=market))
    reservation = safe_path(owner / "experiment-ledgers" / "strategy-robustness" / identity)
    reservation.parent.mkdir(parents=True, exist_ok=True)
    reservation.mkdir(exist_ok=False)
    return reservation


def run_robustness(config, plan_path: Path) -> dict:
    overall = time.monotonic()
    plan = verify_plan(plan_path)
    preflight_elapsed = time.monotonic() - overall
    out = safe_path(plan_path.parent / "run")
    out.mkdir(parents=True, exist_ok=False)
    rows, capacity = [], []
    for market in ("US", "crypto"):
        started = time.monotonic() - preflight_elapsed
        reservation = reserve_market(Path(plan["spec"]["parent_plan"]), plan["spec"]["expected_parent_plan_sha256"], market)
        jobs = [j for j in plan["jobs"] if j["market"] == market]
        write_json(reservation / "attempt.json", dict(plan_sha256=plan["plan_sha256"], phase="started", attempted_jobs=[j["job_id"] for j in jobs]))
        batch = out / f"{market}-batch.json"
        write_json(batch, dict(schema="competition.strategy_robustness_batch.v1", market=market, plan_sha256=plan["plan_sha256"], jobs=jobs))
        project = "equity-lab" if market == "US" else "crypto-mm"
        module = "equity_lab.study.robustness_cli" if market == "US" else "crypto_mm.daily.robustness_cli"
        destination = out / market
        try:
            left = 600 - (time.monotonic() - started)
            if left <= 0:
                raise TimeoutError
            child = run_child([str(interpreter(config, project)), "-m", module, "--batch", str(batch), "--output-root", str(destination)], environment=child_environment(config), timeout=left)
            write_json(reservation / "process.json", dict(returncode=child.returncode, elapsed_seconds=time.monotonic() - started))
        except (OSError, subprocess.TimeoutExpired, TimeoutError):
            child = None
        for job in jobs:
            row = dict(job_id=job["job_id"], market=market, arm_id=job["input_job"]["arm_id"], pool_id=job["pool_id"], fee_bps=job["fee_bps"], start=job["input_job"]["fold"]["start"], end=job["input_job"]["fold"]["end"], status="blocked", reason="FAILED_OR_TIME_BUDGET", metrics=None, benchmark=None, result_path=None)
            try:
                if time.monotonic() - started >= 600 or child is None:
                    raise ValueError("TIME_BUDGET")
                path = destination / job["job_id"] / "result.json"
                value = verify_robustness_result(job, path)
                if market == "crypto":
                    from .capacity import capacity_diagnostics
                    capacity.extend(capacity_diagnostics(job, read_json(path.parent / "periods.json"), None)["checks"])
                if time.monotonic() - started >= 600:
                    raise ValueError("TIME_BUDGET")
                row.update(status="completed", reason=None, metrics=value["metrics"], benchmark=value.get("benchmark"), result_path=path.relative_to(out).as_posix())
            except (ValueError, OSError, KeyError, TypeError):
                pass
            rows.append(row)
        write_json(reservation / "attempt.json", dict(plan_sha256=plan["plan_sha256"], phase="terminal", elapsed_seconds=time.monotonic() - started, completed=sum(r["market"] == market and r["status"] == "completed" for r in rows), attempted_jobs=[j["job_id"] for j in jobs]))
    value = dict(schema="competition.strategy_robustness_results.v1", plan_sha256=plan["plan_sha256"], status="completed" if all(r["status"] == "completed" for r in rows) else "partial", elapsed_seconds=time.monotonic() - overall, jobs=rows, capacity=capacity)
    write_json(out / "results.json", value)
    return value
