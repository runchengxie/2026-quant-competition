"""Freeze explicit missing-day requests; never acquire or register availability."""

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .binance_daily import PRODUCTS, daily_archive_url
from .daily_storage import safe_path
from .quality import validate_bars
from .storage import digest, spec_hash, verify_manifest, write_json

BUDGET = dict(
    attempts=600,
    transferred_bytes=128 * 1024**2,
    expanded_bytes=256 * 1024**2,
    per_zip_bytes=4 * 1024**2,
    seconds=600,
)


def parent_rows(path: Path) -> tuple[dict, dict]:
    path = safe_path(path)
    header = json.loads(path.read_text(encoding="utf-8"))
    if header.get("schema") == "competition.daily_recovery_manifest.v1":
        from .daily_recovery import inspect_recovery

        recovered = inspect_recovery(path)
        ancestor, _ = parent_rows(
            Path(recovered["plan"]["original_plan"]["parent_manifest"])
        )
        manifest = dict(spec=ancestor["spec"], status=recovered["parent_status"])
    elif header.get("schema") == "competition.binance_daily_manifest.v1":
        from .binance_daily_acquisition import inspect_daily_extension

        extension = inspect_daily_extension(path)
        ancestor, _ = parent_rows(Path(extension["plan"]["parent_manifest"]))
        manifest = dict(spec=ancestor["spec"], status=extension["parent_status"])
    else:
        manifest = verify_manifest(path)
    spec = manifest["spec"]
    if (
        tuple(
            spec[k]
            for k in (
                "source",
                "market",
                "quote_currency",
                "calendar",
                "timezone",
                "price_basis",
            )
        )
        != ("binance_spot", "crypto", "USDT", "365", "UTC", "raw")
        or set(spec["products"]) != PRODUCTS
    ):
        raise ValueError("INCOMPATIBLE_DAILY_PARENT")
    tables = {}
    for product in sorted(PRODUCTS):
        with safe_path(path.parent / "normalized" / f"{product}.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_DAILY_PARENT_HEADER")
            rows = list(reader)
        validate_bars(rows)
        if not rows:
            raise ValueError("EMPTY_DAILY_PARENT")
        tables[product] = rows
    return manifest, tables


def freeze_daily_extension(
    spec: dict, base_manifest: Path, output: Path, *, now: datetime
) -> dict:
    if (
        set(spec) != {"schema", "start", "end", "parent_sha256"}
        or spec["schema"] != "competition.binance_daily_extension.v1"
    ):
        raise ValueError("INVALID_DAILY_EXTENSION_SPEC")
    if now.tzinfo is None:
        raise ValueError("UTC_CLOCK_REQUIRED")
    start, end = (date.fromisoformat(spec[k]) for k in ("start", "end"))
    if (
        not 1 <= (end - start).days + 1 <= 31
        or end >= now.astimezone(timezone.utc).date()
    ):
        raise ValueError("INVALID_DAILY_EXTENSION_RANGE")
    parent = safe_path(base_manifest)
    out = safe_path(output)
    if digest(parent) != spec["parent_sha256"]:
        raise ValueError("DAILY_PARENT_CHANGED")
    manifest, tables = parent_rows(parent)
    # A fixed contiguous extension cannot silently overlap or skip a product tail.
    if any(
        date.fromisoformat(rows[-1][0]) + timedelta(days=1) != start
        for rows in tables.values()
    ):
        raise ValueError("DAILY_EXTENSION_MUST_FOLLOW_ALL_PARENT_TAILS")
    resources = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        for product in sorted(PRODUCTS):
            url = daily_archive_url(product, day)
            for suffix in ("", ".CHECKSUM"):
                resources.append(dict(product=product, day=day, url=url + suffix))
    value = dict(
        schema="competition.binance_daily_plan.v1",
        frozen_at=now.isoformat(),
        parent_manifest=str(parent),
        parent_sha256=spec["parent_sha256"],
        parent_status=manifest["status"],
        start=start.isoformat(),
        end=end.isoformat(),
        resources=resources,
        budget=dict(BUDGET),
        accepted_research=False,
    )
    value["plan_sha256"] = spec_hash(value)
    if digest(parent) != spec["parent_sha256"]:
        raise ValueError("DAILY_PARENT_CHANGED")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "plan.json", value)
    return value


def load_daily_plan(path: Path) -> dict:
    value = json.loads(safe_path(path).read_text(encoding="utf-8"))
    content = {k: v for k, v in value.items() if k != "plan_sha256"}
    if (
        value.get("schema") != "competition.binance_daily_plan.v1"
        or spec_hash(content) != value.get("plan_sha256")
        or value.get("budget") != BUDGET
        or value.get("accepted_research") is not False
    ):
        raise ValueError("INVALID_DAILY_PLAN")
    start, end = date.fromisoformat(value["start"]), date.fromisoformat(value["end"])
    if not 1 <= (end - start).days + 1 <= 31:
        raise ValueError("INVALID_DAILY_PLAN_RANGE")
    expected = [
        dict(
            product=p,
            day=(start + timedelta(days=i)).isoformat(),
            url=daily_archive_url(p, (start + timedelta(days=i)).isoformat()) + suffix,
        )
        for i in range((end - start).days + 1)
        for p in sorted(PRODUCTS)
        for suffix in ("", ".CHECKSUM")
    ]
    if (
        value["resources"] != expected
        or digest(safe_path(Path(value["parent_manifest"]))) != value["parent_sha256"]
    ):
        raise ValueError("DAILY_PLAN_IDENTITY_CHANGED")
    return value
