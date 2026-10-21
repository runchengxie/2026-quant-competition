"""Optional study CLI with configuration-free help."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run an explicit frozen daily equity study job"
    )
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    from .inputs import run_job

    try:
        from .inputs import _external

        schema = json.loads(_external(args.job).read_text(encoding="utf-8-sig")).get(
            "schema"
        )
        if schema == "competition.daily_study_job.v2":
            from .ablation_inputs import run_ablation_job

            result = run_ablation_job(args.job, args.output_root)
        else:
            result = run_job(args.job, args.output_root)
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["INVALID_STUDY_JOB_OR_INPUT"]}
            )
        )
        return 2
    print(json.dumps({"status": "completed", "schema": result["schema"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
