"""Explicit bounded daily equity identity, separate from v1 pilot semantics."""

from datetime import date
from pathlib import Path

from competition_tools.team.gateway_verification import validate_contracts
from .spec import identifier

MARKETS = {
    "US": ("USD", "XNYS", "America/New_York", "SMART"),
    "HK": ("HKD", "XHKG", "Asia/Hong_Kong", "SEHK"),
}
KEYS = set(
    "schema dataset_id version source market products benchmark quote_currency start end timezone calendar price_basis universe_status budget connection_file contracts".split()
)


def validate_daily_spec(value: dict) -> None:
    try:
        if not isinstance(value, dict) or set(value) != KEYS:
            raise ValueError
        if (
            value["schema"] != "competition.dataset_spec.v2"
            or value["source"] != "ibkr_daily"
            or value["market"] not in MARKETS
        ):
            raise ValueError
        currency, calendar, zone, exchange = MARKETS[value["market"]]
        if (
            value["quote_currency"],
            value["calendar"],
            value["timezone"],
            value["price_basis"],
            value["universe_status"],
        ) != (currency, calendar, zone, "split_adjusted", "fixed_current"):
            raise ValueError
        if not all(
            identifier(value[k]) for k in ("dataset_id", "version", "benchmark")
        ):
            raise ValueError
        products = value["products"]
        if (
            not isinstance(products, list)
            or not 1 <= len(products) <= 20
            or not all(identifier(p) for p in products)
            or len(set(products)) != len(products)
            or value["benchmark"] in products
        ):
            raise ValueError
        if (
            date.fromisoformat(value["start"]).isoformat() != value["start"]
            or date.fromisoformat(value["end"]).isoformat() != value["end"]
            or value["start"] > value["end"]
        ):
            raise ValueError
        budget = value["budget"]
        caps = {"requests": 120, "bytes": 33554432, "seconds": 2400}
        if (
            not isinstance(budget, dict)
            or set(budget) != set(caps)
            or any(
                type(budget[k]) is not int or not 0 < budget[k] <= caps[k] for k in caps
            )
        ):
            raise ValueError
        if (
            not isinstance(value["connection_file"], str)
            or not Path(value["connection_file"]).is_absolute()
        ):
            raise ValueError
        contracts = validate_contracts(value["contracts"])
        if {c["product"] for c in contracts} != set(
            products + [value["benchmark"]]
        ) or len({c["symbol"] for c in contracts}) != len(contracts):
            raise ValueError
        for contract in contracts:
            if (contract["exchange"], contract["currency"], contract["role"]) != (
                exchange,
                currency,
                "benchmark" if contract["product"] == value["benchmark"] else "stock",
            ):
                raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("INVALID_DAILY_SPEC") from None
