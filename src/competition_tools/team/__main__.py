"""Stdlib-only portable team CLI."""

import argparse
import json
from pathlib import Path

from .config import init_config, load_config
from .processes import envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Configure and run independent offline research"
    )
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init", help="Create an external private configuration")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--data-root", type=Path, required=True)
    init.add_argument("--environment-root", type=Path)
    install = commands.add_parser("setup", help="Install a selected locked profile")
    install.add_argument("--config", type=Path, required=True)
    install.add_argument(
        "--profile",
        choices=["offline", "framework", "broker-data", "website"],
        default="offline",
    )
    install.add_argument(
        "--repository-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    doctor = commands.add_parser(
        "doctor", help="Check local environment readiness without network access"
    )
    doctor.add_argument("--config", type=Path, required=True)
    demo = commands.add_parser("demo", help="Run explicitly synthetic offline examples")
    demo.add_argument("project", choices=["equity", "crypto"])
    demo.add_argument("--config", type=Path, required=True)
    demo.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "init":
            init_config(args.config, args.data_root, args.environment_root)
            value = envelope(args.action)
        else:
            config = load_config(args.config)
            if args.action == "setup":
                from .setup import setup

                value = setup(config, args.repository_root, args.profile)
            elif args.action == "doctor":
                from .doctor import diagnose

                value = diagnose(config)
            else:
                from .demo import run_demo

                value = run_demo(args.project, config, args.output_root)
    except ValueError:
        value = envelope(args.action, issues=["INVALID_CONFIGURATION"])
    print(json.dumps(value))
    return 0 if value["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
