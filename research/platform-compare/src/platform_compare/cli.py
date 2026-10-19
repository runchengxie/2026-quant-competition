"""Run optional diagnostic accounting or verify an owner bundle."""

import argparse
import json
from pathlib import Path


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(
            2,
            json.dumps({"status": "blocked", "issue_codes": ["INVALID_ARGUMENTS"]})
            + "\n",
        )


def main():
    parser = SafeParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--dataset-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--request", type=Path, required=True)
    verify.add_argument("--dataset-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        from platform_compare.owner_adapter import run_request, verify_result

        if args.command == "run":
            value = run_request(args.request, args.dataset_root, args.output)
        else:
            value = verify_result(args.request, args.dataset_root, args.bundle)
        print(json.dumps(value, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, ImportError, OverflowError):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "issue_codes": ["ACCOUNTING_INPUT_OR_BUNDLE_INVALID"],
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
