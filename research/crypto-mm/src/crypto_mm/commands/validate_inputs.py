"""Inspect explicit event-data manifests and write private input receipts."""

import argparse
import json
from pathlib import Path


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(
            2,
            json.dumps({"status": "blocked", "issue_codes": ["INVALID_ARGUMENTS"]})
            + "\n",
        )


def main() -> int:
    from crypto_mm.research.input_validation import validate_inputs
    from polars.exceptions import PolarsError

    parser = _SafeParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = validate_inputs(args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"status": "inspected", "fingerprint": value["fingerprint"]}))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError, PolarsError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["INPUT_INSPECTION_FAILED"]}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
