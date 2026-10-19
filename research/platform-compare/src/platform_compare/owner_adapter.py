"""Call and verify the pinned public owner without copying its accounting."""

import importlib.metadata
import json
from pathlib import Path
from platform_compare.contracts import (
    PIN,
    PROVIDER,
    load_request,
    owner_request,
    check_source,
    clock,
)


def verify_provider():
    for package, subdir in [
        ("quant-platform", None),
        ("research-contracts", "packages/research-contracts"),
    ]:
        dist = importlib.metadata.distribution(package)
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        if (
            direct.get("url")
            not in (
                "https://github.com/runchengxie/quant-platform.git",
                "https://github.com/runchengxie/quant-platform",
            )
            or direct.get("vcs_info", {}).get("commit_id") != PIN
            or direct.get("subdirectory") != subdir
        ):
            raise ValueError("INSTALLED_PROVIDER_MISMATCH")


def verify_bundle(path: Path):
    verify_provider()
    from portfolio_backtester.backtest_bundle_io import read_backtest_bundle

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


def run_request(path: Path, dataset_root: Path, output: Path) -> dict:
    request, asset, source = load_request(path, dataset_root)
    if output.exists():
        raise ValueError("OUTPUT_EXISTS")
    verify_provider()
    from portfolio_backtester.usd_ledger import run_usd_price_replay
    from portfolio_backtester.usd_ledger_bundle import write_usd_price_replay_bundle

    result = run_usd_price_replay(owner_request(request, asset))
    check_source(source, request["input_ref"])
    write_usd_price_replay_bundle(
        output,
        result=result,
        run_id=request["run_id"],
        research_clock=clock(asset["research_clock"]),
        producer={
            "repository": "2026-quant-competition",
            "version": "0.1.0",
            "commit": "unknown",
            "backend": "usd.price_ledger",
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
    return verify_result(path, dataset_root, output)


def verify_result(path: Path, dataset_root: Path, output: Path) -> dict:
    """Derive a projection from hashed owner diagnostics, never an extra sidecar."""
    from decimal import Decimal, localcontext
    import hashlib
    from platform_compare.contracts import digest

    money = owner_decimal

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
        or manifest.backend != {"name": "usd.price_ledger", "version": "1"}
        or manifest.evidence_tier.value != "diagnostic"
        or "diagnostics.json" not in {item.path for item in manifest.inventory}
    ):
        raise ValueError("BUNDLE_REQUEST_MISMATCH")
    diagnostics = json.loads(
        (output / "diagnostics.json").read_text(encoding="utf-8"), parse_float=Decimal
    )
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
        "schema_version": "competition.accounting_result.v1",
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
