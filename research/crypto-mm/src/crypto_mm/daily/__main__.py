"""Offline daily diagnostics; never broker-connected."""

import argparse
import hashlib
import json
from pathlib import Path

from .evaluation import evaluate
from .inputs import load_daily


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--strategy", choices=["equal_weight", "momentum_63d"], required=True
    )
    parser.add_argument("--fee-bps", type=float, default=10)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--products", nargs="+", help="Explicit subset of manifest products"
    )
    args = parser.parse_args(argv)
    output = args.output_root.expanduser().resolve()
    if not args.output_root.is_absolute() or any(
        (p / ".git").exists() for p in (output, *output.parents)
    ):
        parser.error("An absolute external output directory is required")
    bars = load_daily(args.manifest, products=args.products)
    result = evaluate(bars, args.strategy, fee_bps=args.fee_bps)
    result.update(
        manifest_sha256=bars["manifest_sha256"],
        universe_status=bars["universe_status"],
        source_sha256=hashlib.sha256(
            Path(__file__).with_name("evaluation.py").read_bytes()
        ).hexdigest(),
        source_files_sha256={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
        method_version="crypto-daily.v1",
    )
    output.mkdir(parents=True, exist_ok=False)
    with (output / "result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(
        json.dumps({k: v for k, v in result.items() if k != "periods"}, allow_nan=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
