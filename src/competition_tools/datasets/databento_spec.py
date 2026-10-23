"""Fixed, unadjusted daily ingestion pilot, separate from accepted studies."""

import hashlib
import json
import os
from pathlib import Path

SYMBOLS = ["SPY", "QQQ", "IWM", "TLT", "GLD", "AAPL", "MSFT", "NVDA", "AMZN", "META"]
SCHEMA = "competition.databento_dataset_spec.v1"
BUDGET = {
    "metadata_requests": 5,
    "download_requests": 1,
    "bytes": 20971520,
    "seconds": 120,
    "max_cost_usd": "0.10",
}


def safe_path(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("EXTERNAL_ABSOLUTE_PATH_REQUIRED")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or os.path.isjunction(parent)):
            raise ValueError("REPARSE_PATH_REJECTED")
        marker = parent / ".git"
        if marker.is_file() or (marker.is_dir() and any(marker.iterdir())):
            raise ValueError("REPOSITORY_PATH_REJECTED")
    return path


def pilot_spec(credential_file: Path) -> dict:
    return {
        "schema": SCHEMA,
        "dataset_id": "databento-us-daily-pilot",
        "version": "20261023-v1",
        "source": "databento",
        "dataset": "EQUS.SUMMARY",
        "provider_schema": "ohlcv-1d",
        "symbols": list(SYMBOLS),
        "stype_in": "raw_symbol",
        "start": "2025-01-01",
        "end": "2026-01-01",
        "quote_currency": "USD",
        "price_basis": "raw",
        "universe_status": "fixed_current",
        "credential_file": str(credential_file),
        "budget": dict(BUDGET),
    }


def validate_spec(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != set(
        pilot_spec(Path("/placeholder"))
    ):
        raise ValueError("INVALID_DATABENTO_SPEC")
    expected = pilot_spec(Path(value["credential_file"]))
    if value != expected:
        raise ValueError("UNSUPPORTED_PILOT_SCOPE")
    # bool compares equal to int; exact JSON types are contractual.
    if any(type(value["budget"][k]) is not type(v) for k, v in BUDGET.items()):
        raise ValueError("INVALID_BUDGET")
    safe_path(Path(value["credential_file"]))


def request_parameters(spec: dict) -> dict:
    validate_spec(spec)
    return {
        "dataset": spec["dataset"],
        "schema": spec["provider_schema"],
        "symbols": ",".join(spec["symbols"]),
        "stype_in": spec["stype_in"],
        "start": spec["start"],
        "end": spec["end"],
        "limit": 4000,
    }


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def plan(value: dict) -> dict:
    parameters = request_parameters(value)
    return {
        "source": "databento",
        "price_basis": "raw",
        "accepted_research": False,
        "download_parameters": parameters,
        "request_sha256": fingerprint(parameters),
        "budget": dict(BUDGET),
        "status": "preflight_required",
    }
