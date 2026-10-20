"""Run and verify the competition-owned accounting engine."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from platform_compare.contracts import (
    PROVIDER,
    load_request,
    owner_request,
    check_source,
    clock,
)


def verify_bundle(path: Path):
    from platform_compare.accounting.backtest_bundle_io import read_backtest_bundle

    return read_backtest_bundle(path, verify_hashes=True)


def decimal_text(value):
    value = format(value, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def owner_decimal(value):
    """Read finite Decimal strings from an already hash-verified owner inventory."""
    from decimal import Decimal
    import re

    if (
        not isinstance(value, str)
        or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?", value) is None
    ):
        raise ValueError("INVALID_OWNER_DECIMAL")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("INVALID_OWNER_DECIMAL")
    return result


def external_output(output):
    output = Path(output).resolve()
    if any((parent / ".git").exists() for parent in (output, *output.parents)):
        raise ValueError("OUTPUT_IN_SOURCE")
    return output


def _publish(output, request, asset, source):
    from platform_compare.accounting.usd_ledger import run_usd_price_replay
    from platform_compare.accounting.usd_ledger_bundle import write_usd_price_replay_bundle

    result = run_usd_price_replay(owner_request(request, asset))
    check_source(source, request["input_ref"])
    write_usd_price_replay_bundle(
        output,
        result=result,
        run_id=request["run_id"],
        research_clock=clock(asset["research_clock"]),
        producer={
            "repository": "2026-quant-competition",
            "version": "0.2.0",
            "commit": "unknown",
            "backend": "competition.usd_price_ledger",
            "backend_version": "1",
        },
        configuration_sha256=request["config_fingerprint"],
        input_refs=[
            {
                "artifact_id": request["input_ref"]["artifact_id"],
                "sha256": request["input_fingerprint"],
            }
        ],
    )


def run_request(path: Path, dataset_root: Path, output: Path) -> dict:
    output = external_output(output)
    request, asset, source = load_request(path, dataset_root)
    if output.exists():
        raise ValueError("OUTPUT_EXISTS")
    _publish(output, request, asset, source)
    return verify_result(path, dataset_root, output)


def verify_result(path: Path, dataset_root: Path, output: Path) -> dict:
    """Derive a projection from hashed owner diagnostics, never an extra sidecar."""
    from decimal import Decimal, localcontext
    import hashlib
    from platform_compare.contracts import digest

    money = owner_decimal

    output = external_output(output)
    request, asset, source = load_request(path, dataset_root)
    manifest = verify_bundle(output)
    expected_refs = (
        {
            "artifact_id": request["input_ref"]["artifact_id"],
            "sha256": request["input_fingerprint"],
        },
    )
    if (
        manifest.run_id != request["run_id"]
        or manifest.input_refs != expected_refs
        or manifest.artifact_envelope["configuration_sha256"]
        != request["config_fingerprint"]
        or manifest.research_clock != clock(asset["research_clock"]).to_mapping()
        or manifest.backend != {"name": "competition.usd_price_ledger", "version": "1"}
        or manifest.evidence_tier.value != "diagnostic"
        or "diagnostics.json" not in {item.path for item in manifest.inventory}
    ):
        raise ValueError("BUNDLE_REQUEST_MISMATCH")
    diagnostics = json.loads(
        (output / "diagnostics.json").read_text(encoding="utf-8"), parse_float=Decimal
    )
    # Hashes establish integrity, not that a mutable manifest describes the actual
    # calculation. Reproduce the entire request with the public owner APIs and its
    # independent publisher. Temporary files stay in the explicitly supplied data
    # directory and are never written to a source checkout.
    with TemporaryDirectory(prefix=".owner-verify-", dir=output.parent) as temporary:
        expected = Path(temporary) / "bundle"
        _publish(expected, request, asset, source)
        verify_bundle(expected)
        replayed = json.loads(
            (expected / "diagnostics.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        if replayed != diagnostics:
            raise ValueError("BUNDLE_REPLAY_MISMATCH")
    daily = diagnostics["daily"]
    if not daily or diagnostics["summary"]["orders_submitted"] is not False:
        raise ValueError("INVALID_DIAGNOSTIC_BUNDLE")
    with localcontext() as context:
        context.prec = 50
        costs = sum((money(row["costs_usd"]) for row in daily), Decimal(0))
        notional = sum(
            (money(row["notional_usd"]) for row in diagnostics["transactions"]),
            Decimal(0),
        )
    check_source(source, request["input_ref"])
    return {
        "schema_version": "competition.accounting_result.v2",
        "status": "diagnostic",
        "provider": PROVIDER,
        "market": request["market"],
        "synthetic": request["synthetic"],
        "input_fingerprint": request["input_fingerprint"],
        "upstream_input_fingerprint": asset["upstream_input_fingerprint"],
        "config_fingerprint": request["config_fingerprint"],
        "schedule_fingerprint": digest(asset["decisions"]),
        "manifest_fingerprint": hashlib.sha256(
            (output / "manifest.json").read_bytes()
        ).hexdigest(),
        "initial_cash_usd": diagnostics["accounting"]["initial_cash_usd"],
        "final_nav_usd": decimal_text(money(daily[-1]["nav_usd"])),
        "final_cash_usd": decimal_text(money(daily[-1]["cash_usd"])),
        "final_positions_usd": decimal_text(money(daily[-1]["positions_usd"])),
        "total_costs_usd": decimal_text(costs),
        "traded_notional_usd": decimal_text(notional),
        "sizing_mode": diagnostics["accounting"]["sizing_mode"],
        "cost_assumptions": {
            key: request["config"][key]
            for key in ("commission_bps", "slippage_bps", "fx_cost_bps")
        },
        "return_basis": "usd_price_nav",
        "orders_submitted": False,
        "observations": len(daily),
        "transactions": len(diagnostics["transactions"]),
        "order_lifecycle": False,
    }
