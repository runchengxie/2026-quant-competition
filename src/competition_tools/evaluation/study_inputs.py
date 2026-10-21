"""Verify consumed daily inputs without importing a research package."""

import csv
from datetime import date, timedelta
from pathlib import Path

from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.quality import validate_bars
from competition_tools.datasets.spec import identifier
from competition_tools.datasets.storage import verify_manifest, digest


def load_study_input(path: Path) -> dict:
    path = safe_path(path)
    manifest = verify_manifest(path)
    spec = manifest["spec"]
    market = spec["market"]
    crypto = market == "crypto"
    expected = (
        ("binance_spot", "USDT", "365", "UTC", "raw")
        if crypto
        else {
            "US": ("ibkr_daily", "USD", "XNYS", "America/New_York", "split_adjusted"),
            "HK": ("ibkr_daily", "HKD", "XHKG", "Asia/Hong_Kong", "split_adjusted"),
        }.get(market)
    )
    if (
        expected is None
        or tuple(
            spec[k]
            for k in ("source", "quote_currency", "calendar", "timezone", "price_basis")
        )
        != expected
        or spec["universe_status"] != "fixed_current"
    ):
        raise ValueError("INCOMPATIBLE_STUDY_INPUT")
    if not crypto and (
        manifest["schema"] != "competition.dataset_manifest.v2"
        or manifest["status"] != "acquired"
    ):
        raise ValueError("COMPLETE_EQUITY_MANIFEST_REQUIRED")
    if crypto and manifest["schema"] != "competition.dataset_manifest.v1":
        raise ValueError("INCOMPATIBLE_STUDY_INPUT")
    products = spec["products"]
    if (
        not isinstance(products, list)
        or not 1 <= len(products) <= 20
        or not all(identifier(p) for p in products)
        or len(set(products)) != len(products)
    ):
        raise ValueError("INVALID_STUDY_PRODUCTS")
    selected = list(products)
    benchmark = "equal_weight" if crypto else spec["benchmark"]
    if not crypto:
        if not identifier(benchmark) or benchmark in products:
            raise ValueError("INVALID_STUDY_BENCHMARK")
        selected.append(benchmark)
    records = {r["path"]: r for r in manifest["files"]}
    tables, files = {}, []
    for product in selected:
        relative = f"normalized/{product}.csv"
        if relative not in records:
            raise ValueError("PRODUCT_COVERAGE_MISSING")
        with safe_path(path.parent / relative).open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_STUDY_HEADER")
            rows = list(reader)
        validate_bars(rows)
        if not rows:
            raise ValueError("EMPTY_STUDY_INPUT")
        tables[product] = {r[0]: float(r[4]) for r in rows}
        files.append(records[relative])
    start = max("2023-01-01", spec["start"])
    end = spec["end"]
    if crypto:
        start = max(start, *(min(t) for t in tables.values()))
        end = min(end, *(max(t) for t in tables.values()))
        count = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        dates = [
            (date.fromisoformat(start) + timedelta(days=i)).isoformat()
            for i in range(max(0, count))
        ]
    else:
        dates = [
            d for d in manifest["receipt"]["calendar"]["sessions"] if start <= d <= end
        ]
    if not dates or dates != sorted(set(dates)):
        raise ValueError("INVALID_STUDY_GRID")
    if any(
        [d for d in table if start <= d <= end] != dates for table in tables.values()
    ):
        raise ValueError("INCOMPLETE_STUDY_GRID")
    parent_hash = digest(path)
    return {
        "market": market,
        "quote_currency": spec["quote_currency"],
        "manifest": str(path),
        "manifest_sha256": parent_hash,
        "products": products,
        "benchmark": benchmark,
        "dates": dates,
        "input_files": files,
        "parent_status": manifest["status"],
        "slice": {
            "schema": "competition.study_input_slice.v1",
            "parent_sha256": parent_hash,
            "parent_status": manifest["status"],
            "products": products,
            "start": dates[0],
            "end": dates[-1],
            "files": files,
            "selection": "fixed_current_from_2023",
            "accepted_research": False,
        },
    }
