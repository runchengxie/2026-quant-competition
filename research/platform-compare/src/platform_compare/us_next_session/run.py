"""Offline modeled US price NAV. No broker connection or order API."""

import argparse
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from ..accounting.usd_ledger import run_usd_price_replay
from ..accounting.usd_ledger_bundle import write_usd_price_replay_bundle
from ..owner_adapter import external_output
from .adapter import MODEL_ID, build_us_replay_request
from .inputs import load_us_inputs


def run(config_path, output, *, fee_bps=Decimal(20)):
    inputs = load_us_inputs(config_path)
    request = build_us_replay_request(inputs, fee_bps=fee_bps)
    result = run_usd_price_replay(request)
    if load_us_inputs(config_path).input_hashes != inputs.input_hashes:
        raise ValueError("INPUT_HASH_CHANGED")
    target = external_output(output)
    target.mkdir(parents=True, exist_ok=False)
    clock = replace(
        request.decisions[0].clock,
        valuation_at=result.daily.iloc[-1].valuation_at,
        execution_window_end_at=max(
            t for d in request.decisions for t in d.execution_times.values()
        ),
    )
    write_usd_price_replay_bundle(
        target / "bundle",
        result=result,
        run_id=MODEL_ID,
        research_clock=clock,
        producer=dict(
            repository="2026-quant-competition",
            version="1",
            commit="unknown",
            backend="competition.usd_price_ledger",
            backend_version="1",
        ),
        configuration_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        input_refs=[
            dict(
                artifact_id=f"us-price:{k}",
                sha256=inputs.schedule["files"][k]["sha256"],
            )
            for k in inputs.assets
        ],
    )
    value = dict(
        schema="competition.us_next_session_run.v1",
        status="completed",
        model_id=MODEL_ID,
        synthetic=inputs.schedule["synthetic"],
        return_basis="usd_price_nav",
        orders_submitted=0,
        execution_eligible=False,
        total_return=False,
        fee_bps=str(fee_bps),
        input_hashes=inputs.input_hashes,
    )
    with (target / "run.json").open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--output-root", "--output-dir", dest="output_root", type=Path, required=True
    )
    parser.add_argument("--fee-bps", type=Decimal, default=Decimal(20))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        value = run(args.config, args.output_root, fee_bps=args.fee_bps)
    except (ValueError, OSError, TypeError, KeyError):
        print(
            json.dumps(
                dict(status="blocked", issue_codes=["INVALID_US_EXECUTION_INPUT"])
            )
        )
        return 2
    print(json.dumps(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
