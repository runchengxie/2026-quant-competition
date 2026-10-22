"""Explicit intraday DEX identities; independent of the daily dataset contracts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from competition_tools.team.paths import validate_external
from .spec import identifier

SCHEMA = "competition.dex_dataset_spec.v1"
CAPS = {"requests": 100, "bytes": 52428800, "seconds": 900, "requests_per_minute": 20}


def safe_path(value: str | Path, *, external: bool = True) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or ".." in path.parts or path.anchor.startswith("\\\\"):
        raise ValueError("INVALID_DEX_PATH")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("DEX_REPARSE_PATH")
    return validate_external(path) if external else path.resolve()


def utc_hour(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:00:00Z", value
    ):
        raise ValueError("INVALID_UTC_HOUR")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def address_valid(network: str, address: str) -> bool:
    if not isinstance(address, str):
        return False
    if network == "ethereum":
        return re.fullmatch(r"0x[0-9a-f]{40}", address) is not None
    if network == "solana":
        return re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", address) is not None
    return False


def dataset_identity(value: dict) -> dict:
    return {
        key: value[key]
        for key in (
            "dataset_id",
            "version",
            "source",
            "interval",
            "quote_currency",
            "selection",
            "start",
            "end",
            "assets",
        )
    }


def validate_dex_spec(value: dict) -> None:
    required = {
        "schema",
        "dataset_id",
        "version",
        "source",
        "interval",
        "quote_currency",
        "selection",
        "start",
        "end",
        "assets",
        "credential_file",
        "protocol_file",
        "protocol_sha256",
        "budget",
    }
    try:
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError
        if any(
            value[k] != v
            for k, v in {
                "schema": SCHEMA,
                "source": "dexpaprika",
                "interval": "1h",
                "quote_currency": "USD",
                "selection": "fixed_current",
            }.items()
        ):
            raise ValueError
        if not all(identifier(value[k]) for k in ("dataset_id", "version")):
            raise ValueError
        start, end = utc_hour(value["start"]), utc_hour(value["end"])
        if end - start != timedelta(days=90) or end > datetime.now(
            timezone.utc
        ).replace(minute=0, second=0, microsecond=0):
            raise ValueError
        if not isinstance(value["protocol_sha256"], str) or not re.fullmatch(
            "[a-f0-9]{64}", value["protocol_sha256"]
        ):
            raise ValueError
        for key in ("credential_file", "protocol_file"):
            if not isinstance(value[key], str):
                raise ValueError
            safe_path(value[key])
        budget = value["budget"]
        if (
            not isinstance(budget, dict)
            or set(budget) != set(CAPS)
            or any(
                type(budget[k]) is not int or not 0 < budget[k] <= cap
                for k, cap in CAPS.items()
            )
        ):
            raise ValueError
        assets = value["assets"]
        if not isinstance(assets, list) or not 1 <= len(assets) <= 10:
            raise ValueError
        ids, underlyings, pairs = set(), set(), set()
        for asset in assets:
            if (
                not isinstance(asset, dict)
                or not {"stable_id", "underlying_id", "network", "address"}
                <= set(asset)
                or set(asset)
                - {"stable_id", "underlying_id", "network", "address", "pool_address"}
            ):
                raise ValueError
            if not all(
                identifier(asset[k]) for k in ("stable_id", "underlying_id")
            ) or not address_valid(asset["network"], asset["address"]):
                raise ValueError
            if "pool_address" in asset and not address_valid(
                asset["network"], asset["pool_address"]
            ):
                raise ValueError
            pair = (asset["network"], asset["address"])
            if (
                asset["stable_id"] in ids
                or asset["underlying_id"] in underlyings
                or pair in pairs
            ):
                raise ValueError
            ids.add(asset["stable_id"])
            underlyings.add(asset["underlying_id"])
            pairs.add(pair)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("INVALID_DEX_SPEC") from None
