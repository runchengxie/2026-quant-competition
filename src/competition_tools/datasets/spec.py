"""Validate explicit external dataset specifications without provider discovery."""

import json
import re
from datetime import date
from pathlib import Path

SOURCES = {
    "binance_spot",
    "licensed_import",
    "ibkr",
    "algoseek",
    "aivix",
    "index_one",
    "coinpaprika",
}


def identifier(value: str) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value) is not None
    )


def load_spec(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_spec(value)
    return value


def validate_spec(value: dict) -> None:
    if isinstance(value, dict) and value.get("schema") == "competition.dex_dataset_spec.v1":
        from .dex_spec import validate_dex_spec
        return validate_dex_spec(value)
    if isinstance(value, dict) and value.get("schema") == "competition.dataset_spec.v2":
        from .daily_spec import validate_daily_spec
        return validate_daily_spec(value)
    required = {
        "schema",
        "dataset_id",
        "version",
        "source",
        "market",
        "products",
        "quote_currency",
        "start",
        "end",
        "timezone",
        "calendar",
        "price_basis",
        "universe_status",
        "budget",
    }
    if not isinstance(value, dict) or not required <= value.keys():
        raise ValueError("INVALID_SPEC")
    if (
        set(value)
        - required
        - {"credential_file", "membership_file", "input_directory", "contracts"}
    ):
        raise ValueError("UNKNOWN_SPEC_FIELD")
    if (
        value["schema"] != "competition.dataset_spec.v1"
        or value["source"] not in SOURCES
    ):
        raise ValueError("INVALID_SOURCE")
    if not all(
        identifier(value[k]) for k in ("dataset_id", "version", "quote_currency")
    ):
        raise ValueError("INVALID_IDENTITY")
    if value["market"] not in {"crypto", "US", "HK"} or value["price_basis"] not in {
        "raw",
        "adjusted",
        "split_adjusted",
    }:
        raise ValueError("INVALID_MARKET_OR_BASIS")
    if value["universe_status"] not in {"fixed_current", "point_in_time"}:
        raise ValueError("INVALID_UNIVERSE_STATUS")
    if (
        not isinstance(value["products"], list)
        or not value["products"]
        or len(set(value["products"])) != len(value["products"])
    ):
        raise ValueError("INVALID_PRODUCTS")
    if not all(identifier(p) for p in value["products"]):
        raise ValueError("INVALID_PRODUCT")
    if date.fromisoformat(value["start"]) > date.fromisoformat(value["end"]):
        raise ValueError("INVALID_RANGE")
    if (
        not isinstance(value["timezone"], str)
        or not value["timezone"]
        or not isinstance(value["calendar"], str)
    ):
        raise ValueError("INVALID_CALENDAR")
    budget = value["budget"]
    if not isinstance(budget, dict) or set(budget) != {"requests", "bytes", "seconds"}:
        raise ValueError("INVALID_BUDGET")
    caps = (
        {"requests": 5000, "bytes": 1073741824, "seconds": 3600}
        if value["market"] == "crypto"
        else {"requests": 10000, "bytes": 2147483648, "seconds": 7200}
    )
    if any(type(budget[k]) is not int or not 0 < budget[k] <= caps[k] for k in caps):
        raise ValueError("INVALID_BUDGET")
    if value["source"] == "binance_spot":
        if (
            value["market"] != "crypto"
            or value["timezone"] != "UTC"
            or value["calendar"] != "365"
            or value["price_basis"] != "raw"
            or len(value["products"]) > 20
            or value["quote_currency"] != "USDT"
            or any(not re.fullmatch(r"[A-Z0-9]+USDT", p) for p in value["products"])
        ):
            raise ValueError("INVALID_SPOT_IDENTITY")
        if "credential_file" in value:
            raise ValueError("PUBLIC_SOURCE_REJECTS_CREDENTIALS")
    if value["source"] == "ibkr":
        if (
            value["price_basis"] != "split_adjusted"
            or value["market"] not in {"US", "HK"}
            or value["quote_currency"] != ("USD" if value["market"] == "US" else "HKD")
        ):
            raise ValueError("INVALID_BROKER_BASIS_OR_IDENTITY")
