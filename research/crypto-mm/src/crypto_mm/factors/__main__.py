"""Offline factor CLI. No provider or broker credentials are consumed."""

import argparse
import json

from .inputs import external, file_hash, read_json, verify_inputs
from .study import run_factor_study


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run fixed retrospective hourly factor diagnostics"
    )
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    try:
        path = external(args.spec)
        protocol = read_json(path)
        if file_hash(path) != verify_inputs(protocol)["protocol_sha256"]:
            raise ValueError("FACTOR_PROTOCOL_HASH_MISMATCH")
        run_factor_study(protocol, external(args.output_root))
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"status": "blocked", "reason": "FACTOR_STUDY_INVALID_INPUT"}))
        return 2
    print(json.dumps({"status": "completed", "artifact": "result.json"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
