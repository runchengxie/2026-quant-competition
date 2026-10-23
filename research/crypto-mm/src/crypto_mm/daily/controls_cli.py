"""Bounded standalone controls batch CLI with configuration-free help."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    from .controls_inputs import read_json, validate_controls_job, run_controls_job
    from .study_inputs import _external, _write

    try:
        batch = read_json(args.jobs)
        if (
            not isinstance(batch, dict)
            or set(batch) != {"schema", "plan_sha256", "market", "jobs"}
            or batch["schema"] != "competition.strategy_controls_batch.v1"
            or batch["market"] != "crypto"
            or not isinstance(batch["jobs"], list)
            or not 1 <= len(batch["jobs"]) <= 384
        ):
            raise ValueError("INVALID_CONTROLS_BATCH")
        jobs = [validate_controls_job(j) for j in batch["jobs"]]
        if any(j["plan_sha256"] != batch["plan_sha256"] for j in jobs) or len(
            {j["job_id"] for j in jobs}
        ) != len(jobs):
            raise ValueError("INVALID_CONTROLS_BATCH")
        out = _external(args.output_root)
        out.mkdir(parents=True, exist_ok=False)
        (out / "inputs").mkdir()
        records = []
        for job in jobs:
            path = out / "inputs" / (job["job_id"] + ".json")
            _write(path, job)
            try:
                run_controls_job(path, out / job["job_id"])
                records.append(
                    dict(job_id=job["job_id"], status="completed", issue_codes=[])
                )
            except (ValueError, OSError, KeyError, TypeError, IndexError):
                records.append(
                    dict(
                        job_id=job["job_id"],
                        status="blocked",
                        issue_codes=["CONTROLS_JOB_FAILED"],
                    )
                )
        complete = all(r["status"] == "completed" for r in records)
        result = dict(
            schema="competition.strategy_controls_batch_result.v1",
            plan_sha256=batch["plan_sha256"],
            status="completed" if complete else "partial",
            jobs=records,
        )
        _write(out / "batch-result.json", result)
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "issue_codes": ["INVALID_CONTROLS_BATCH_OR_INPUT"],
                }
            )
        )
        return 2
    print(json.dumps({"status": result["status"], "jobs": len(records)}))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
