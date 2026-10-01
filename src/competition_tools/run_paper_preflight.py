from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.execution_runner.preflight import run_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Paper-safe execution preflight")
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--check-gateway", action="store_true")
    parser.add_argument("--gateway-timeout", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_preflight(args.targets, args.config, check_gateway=args.check_gateway, gateway_timeout=args.gateway_timeout)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.overall == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
