"""Run explicitly selected daily jobs in their separate locked leaf environment."""

import json
import subprocess
import time
from pathlib import Path

from .config import TeamConfig
from .paths import validate_external
from .processes import child_environment, interpreter, run_child, envelope
from competition_tools.evaluation.matrix import build_matrix
from competition_tools.datasets.storage import write_json


def execute(config: TeamConfig, spec_path: Path, output_root: Path) -> dict:
    spec = json.loads(validate_external(spec_path).read_text(encoding="utf-8-sig"))
    if (
        set(spec) != {"schema", "manifests"}
        or spec["schema"] != "competition.evaluation_spec.v1"
    ):
        raise ValueError("INVALID_EVALUATION_SPEC")
    jobs = build_matrix([validate_external(Path(p)) for p in spec["manifests"]])
    if not jobs:
        raise ValueError("EMPTY_EVALUATION_MATRIX")
    output = validate_external(output_root)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    records = []
    for index, job in enumerate(jobs):
        remaining = 3600 - (time.monotonic() - started)
        record = dict(job, job_id=index, status="blocked")
        if remaining <= 0:
            record["reason"] = "TIME_BUDGET"
        else:
            destination = output / f"job-{index:02}"
            command = [
                str(interpreter(config, "crypto-mm")),
                "-m",
                "crypto_mm.daily",
                "--manifest",
                job["manifest"],
                "--strategy",
                job["strategy"],
                "--fee-bps",
                str(job["fee_bps"]),
                "--output-root",
                str(destination),
            ]
            try:
                child = run_child(
                    command,
                    environment=child_environment(config),
                    timeout=max(1, int(remaining)),
                )
                if child.returncode == 0 and (destination / "result.json").is_file():
                    record.update(
                        status="completed", result_path=str(destination / "result.json")
                    )
                else:
                    record["reason"] = "DAILY_EVALUATION_FAILED"
            except (OSError, subprocess.TimeoutExpired):
                record["reason"] = "CHILD_UNAVAILABLE_OR_TIMEOUT"
        records.append(record)
        write_json(
            output / "jobs.json",
            {"schema": "competition.strategy_evaluation.v1", "jobs": records},
        )
    return envelope(
        "evaluate",
        issues=[]
        if all(r["status"] == "completed" for r in records)
        else ["EVALUATION_PARTIAL"],
        projects=records,
    )
