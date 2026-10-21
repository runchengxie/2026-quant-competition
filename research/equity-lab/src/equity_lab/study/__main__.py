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
        run_job(args.job, args.output_root)
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["INVALID_STUDY_JOB_OR_INPUT"]}
            )
        )
        return 2
    print(
        json.dumps(
            {"status": "completed", "schema": "competition.daily_study_result.v1"}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
