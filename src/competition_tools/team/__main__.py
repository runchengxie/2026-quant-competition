"""Stdlib-only portable team CLI."""

import argparse
import json
from pathlib import Path

from .config import init_config


def result(
    action: str,
    *,
    issues: list[str] | None = None,
    projects: list | None = None,
    synthetic: bool | None = None,
) -> dict:
    return {
        "schema_version": "competition.team_result.v1",
        "action": action,
        "status": "blocked" if issues else "completed",
        "issue_codes": issues or [],
        "projects": projects or [],
        "synthetic": synthetic,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Configure and run independent offline research"
    )
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init", help="Create an external private configuration")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--data-root", type=Path, required=True)
    init.add_argument("--environment-root", type=Path)
    args = parser.parse_args(argv)
    try:
        init_config(args.config, args.data_root, args.environment_root)
        value = result(args.action)
    except ValueError:
        value = result(args.action, issues=["INVALID_CONFIGURATION"])
    print(json.dumps(value))
    return 0 if value["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
