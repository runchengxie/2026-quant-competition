"""Readiness is separate from provider marketing capability and entitlement."""

from pathlib import Path


def readiness(spec: dict) -> dict:
    source = spec["source"]
    if source == "binance_spot":
        return {
            "source": source,
            "status": "ready",
            "reason": None,
            "kind": "spot_daily",
        }
    if source == "licensed_import":
        exists = Path(spec.get("input_directory", "")).is_dir() and bool(
            spec.get("input_directory")
        )
        return {
            "source": source,
            "status": "ready" if exists else "blocked",
            "reason": None if exists else "INPUT_DIRECTORY_MISSING",
        }
    if source == "ibkr":
        configured = bool(spec.get("credential_file")) and bool(spec.get("contracts"))
        return {
            "source": source,
            "status": "ready" if configured else "blocked",
            "reason": None if configured else "EXPLICIT_PAPER_CONNECTION_REQUIRED",
            "kind": "one_month_pilot",
        }
    # No guessed authenticated endpoints, credential discovery or silent substitutes.
    return {
        "source": source,
        "status": "blocked",
        "reason": "PROVIDER_CONTRACT_UNVERIFIED",
    }
