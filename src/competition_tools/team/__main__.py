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
    gateway = commands.add_parser("gateway", help="Verify Paper reading evidence without login or orders")
    gateway_commands = gateway.add_subparsers(dest="operation", required=True)
    verify = gateway_commands.add_parser("verify", help="Check Paper account prefix, contracts and optional history")
    verify.add_argument("--connection-file", type=Path, required=True)
    verify.add_argument("--contract-spec", type=Path, required=True)
    verify.add_argument("--ini-file", type=Path)
    verify.add_argument("--historical", action="store_true")
    verify.add_argument("--output-root", type=Path)
    init = commands.add_parser("init", help="Create an external private configuration")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--data-root", type=Path, required=True)
    init.add_argument("--environment-root", type=Path)
    install = commands.add_parser("setup", help="Install a selected locked profile")
    install.add_argument("--config", type=Path, required=True)
    install.add_argument(
        "--profile",
        choices=["offline", "framework", "broker-data", "daily-data", "website"],
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
    run = commands.add_parser(
        "run", help="Run an explicitly configured international experiment"
    )
    run.add_argument("project", choices=["international", "next-open", "us-next-session"])
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--experiment-config", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    data = commands.add_parser("data", help="Plan, acquire or inspect explicit offline datasets")
    data.add_argument("operation", choices=["plan", "acquire", "inspect", "refresh"])
    data.add_argument("--config", type=Path, required=True)
    data.add_argument("--spec", type=Path, required=True)
    data.add_argument("--manifest", type=Path)
    data.add_argument("--base-manifest", type=Path, help="Explicit immutable v2 refresh parent")
    data.add_argument("--ensure-gateway", action="store_true", help="Opt in to one authorized Paper login attempt for IBKR acquisition")
    data.add_argument("--gateway-config", type=Path, help="External activated IBC launcher JSON")
    data.add_argument("--gateway-workspace", type=Path, help="Explicit machine workspace.toml")
    data.add_argument("--gateway-wrapper", type=Path, help="External stable Start-PaperGateway.ps1 deployment")
    evaluate = commands.add_parser("evaluate", help="Run bounded retrospective daily diagnostics")
    evaluate.add_argument("--config", type=Path, required=True)
    evaluate.add_argument("--spec", type=Path, required=True)
    evaluate.add_argument("--output-root", type=Path, required=True)
    controls = commands.add_parser("controls", help="Run frozen independent strategy-control experiments")
    controls.add_argument("--config", type=Path, required=True)
    controls.add_argument("--spec", type=Path, required=True)
    controls.add_argument("--output-root", type=Path, required=True)
    readiness = commands.add_parser("execution-readiness", help="Inventory missing US execution evidence without network or orders")
    readiness.add_argument("--config", type=Path, required=True)
    readiness.add_argument("--spec", type=Path, required=True)
    readiness.add_argument("--output-root", type=Path, required=True)
    factors = commands.add_parser("factors", help="Run fixed retrospective hourly factor diagnostics")
    factors.add_argument("--config", type=Path, required=True)
    factors.add_argument("--spec", type=Path, required=True)
    factors.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "gateway":
        from .gateway_verification import execute

        try:
            value = execute(args.connection_file, args.contract_spec, ini_path=args.ini_file,
                            historical=args.historical, output_root=args.output_root)
        except (ValueError, OSError, TypeError, KeyError):
            print(json.dumps({"issue_codes": ["INVALID_VERIFICATION_INPUT"]}))
            return 2
        print(json.dumps(value))
        return 0 if not value["issue_codes"] else 2
    try:
        if args.action == "init":
            init_config(args.config, args.data_root, args.environment_root)
            value = envelope(args.action)
        else:
            config = load_config(args.config)
            if args.action == "execution-readiness":
                from .execution_readiness import execute

                value = execute(config, args.spec, args.output_root)
            elif args.action == "controls":
                from .controls import execute

                value = execute(config, args.spec, args.output_root)
            elif args.action == "factors":
                from .factors import execute

                value = execute(config, args.spec, args.output_root)
            elif args.action == "evaluate":
                from .evaluate import execute

                value = execute(config, args.spec, args.output_root)
            elif args.action == "data":
                from .data import execute

                value = execute(args.operation, config, args.spec, args.manifest,
                                base_manifest=args.base_manifest,
                                ensure_gateway=args.ensure_gateway, gateway_config=args.gateway_config,
                                gateway_workspace=args.gateway_workspace, gateway_wrapper=args.gateway_wrapper)
            elif args.action == "setup":
                from .setup import setup

                value = setup(config, args.repository_root, args.profile)
            elif args.action == "doctor":
                from .doctor import diagnose

                value = diagnose(config)
            elif args.action == "demo":
                from .demo import run_demo

                value = run_demo(args.project, config, args.output_root)
            else:
                from .run import run_experiment

                value = run_experiment(
                    args.project, config, args.experiment_config, args.output_root
                )
    except (ValueError, OSError, TypeError, KeyError):
        value = envelope(
            args.action,
            issues=["INVALID_CONFIGURATION"],
            synthetic=True if args.action == "demo" else None,
        )
    print(json.dumps(value))
    return 0 if value["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
