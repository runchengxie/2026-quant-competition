"""Bounded read-only Paper evidence, separate from readiness and orders."""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from competition_tools import gateway_launcher as gl
from .paper_session import PaperReadError, PaperReadSession
from .paths import validate_external


def validate_contracts(specs):
    if not isinstance(specs, list) or not 1 <= len(specs) <= 21:
        raise ValueError("INVALID_CONTRACT_SPEC")
    products = set()
    markets = set()
    for spec in specs:
        if not isinstance(spec, dict) or set(spec) != {
            "product",
            "symbol",
            "exchange",
            "currency",
            "role",
        }:
            raise ValueError("INVALID_CONTRACT_SPEC")
        if any(not isinstance(value, str) for value in spec.values()):
            raise ValueError("INVALID_CONTRACT_SPEC")
        if not re.fullmatch(
            r"[A-Z0-9][A-Z0-9.\-]{0,19}", spec["product"]
        ) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", spec["symbol"]):
            raise ValueError("INVALID_CONTRACT_SPEC")
        market = (spec["exchange"], spec["currency"])
        if (
            market not in {("SMART", "USD"), ("SEHK", "HKD")}
            or spec["role"] not in {"stock", "benchmark"}
            or spec["product"] in products
        ):
            raise ValueError("INVALID_CONTRACT_SPEC")
        products.add(spec["product"])
        markets.add(market)
    if len(markets) != 1:
        raise ValueError("INVALID_CONTRACT_SPEC")
    return specs


def _stock(spec):
    try:
        from ib_insync import Stock
    except ImportError:
        raise PaperReadError("BROKER_DATA_PROFILE_REQUIRED") from None
    return Stock(spec["symbol"], spec["exchange"], spec["currency"])


def _ini_intent(path):
    path = gl._path(str(path), shell_path=False)
    if not gl.owner_only_acl(path):
        raise gl.LauncherError("UNSAFE_ACL")
    # Existing strict properties parser discards credential values and rejects
    # unknown/duplicate properties. This is configuration intent, not runtime proof.
    gl._ini(path, 300)


def verify_reading(
    connection_file: Path,
    contract_specs: list[dict],
    *,
    ini_path: Path | None = None,
    historical: bool = False,
    client_factory=None,
) -> dict:
    report = {
        "schema_version": "competition.paper_read_verification.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "api": "not_checked",
        "account_prefix": "not_checked",
        "contract": "not_checked",
        "historical": "not_checked",
        "intended_read_only": "not_verified",
        "server_read_only": "not_verified",
        "issue_codes": [],
    }
    try:
        validate_contracts(contract_specs)
    except ValueError:
        report["issue_codes"].append("INVALID_CONTRACT_SPEC")
        return report
    if ini_path is not None:
        try:
            _ini_intent(ini_path)
            report["intended_read_only"] = "enabled"
        except gl.LauncherError as error:
            report["intended_read_only"] = "blocked"
            code = str(error)
            report["issue_codes"].append(
                code
                if code
                in {
                    "UNSAFE_ACL",
                    "REPARSE_PATH",
                    "DUPLICATE_KEY",
                    "UNSAFE_IBC_CONFIGURATION",
                }
                else "INVALID_IBC_CONFIGURATION"
            )
            return report
        except (OSError, ValueError):
            report["intended_read_only"] = "blocked"
            report["issue_codes"].append("INVALID_IBC_CONFIGURATION")
            return report
    stage = "api"
    try:
        with PaperReadSession(connection_file, client_factory=client_factory) as client:
            report["api"] = "connected"
            report["account_prefix"] = "paper_single"
            client.RequestTimeout = 8
            stage = "contract"
            contracts = []
            for spec in contract_specs:
                qualified = client.qualifyContracts(_stock(spec))
                if len(qualified) != 1 or not _matches(qualified[0], spec):
                    raise PaperReadError("CONTRACT_MISMATCH")
                contracts.append(qualified[0])
            report["contract"] = "matched"
            if historical:
                stage = "historical"
                for contract in contracts:
                    bars = client.reqHistoricalData(
                        contract,
                        endDateTime="",
                        durationStr="5 D",
                        barSizeSetting="1 day",
                        whatToShow="TRADES",
                        useRTH=True,
                        formatDate=1,
                        timeout=8,
                    )
                    if not bars or any(not _valid_close(bar) for bar in bars):
                        raise PaperReadError("HISTORICAL_UNAVAILABLE")
                report["historical"] = "available"
            stage = "api"
    except Exception as error:
        code = (
            str(error)
            if isinstance(error, PaperReadError)
            else {
                "api": "API_READ_FAILED",
                "contract": "CONTRACT_READ_FAILED",
                "historical": "HISTORICAL_READ_FAILED",
            }[stage]
        )
        if code == "PAPER_ACCOUNT_REQUIRED":
            report["api"] = "connected"
            report["account_prefix"] = "blocked"
        else:
            report[stage] = "not_ready" if stage == "api" else "blocked"
        report["issue_codes"].append(code)
    return report


def _matches(contract, spec):
    return (
        type(contract.conId) is int
        and contract.conId > 0
        and contract.secType == "STK"
        and contract.symbol == spec["symbol"]
        and contract.exchange == spec["exchange"]
        and contract.currency == spec["currency"]
    )


def _valid_close(bar):
    close = getattr(bar, "close", None)
    return type(close) in (int, float) and math.isfinite(close) and close > 0


def execute(
    connection_file, contract_file, *, ini_path=None, historical=False, output_root=None
):
    payload = json.loads(
        validate_external(contract_file).read_text(encoding="utf-8-sig")
    )
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "market", "contracts"}
        or payload["schema"] != "competition.paper_contract_spec.v1"
        or payload["market"] not in {"US", "HK"}
    ):
        raise ValueError("INVALID_CONTRACT_SPEC")
    specs = validate_contracts(payload["contracts"])
    if any(
        spec["currency"] != {"US": "USD", "HK": "HKD"}[payload["market"]]
        for spec in specs
    ):
        raise ValueError("INVALID_CONTRACT_SPEC")
    destination = validate_external(output_root) if output_root is not None else None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=False)
    report = verify_reading(
        connection_file, specs, ini_path=ini_path, historical=historical
    )
    if destination is not None:
        (destination / "verification.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    return report
