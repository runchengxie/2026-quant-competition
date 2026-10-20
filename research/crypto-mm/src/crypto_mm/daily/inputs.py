"""Consume immutable daily manifests without importing the root project."""

import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path, PurePosixPath


def load_daily(manifest_path: Path, *, products: list[str] | None = None) -> dict:
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest["spec"]
    if (
        manifest["schema"] != "competition.dataset_manifest.v1"
        or spec["source"] != "binance_spot"
        or spec["market"] != "crypto"
        or spec["calendar"] != "365"
        or spec["timezone"] != "UTC"
        or spec["quote_currency"] != "USDT"
        or spec["price_basis"] != "raw"
    ):
        raise ValueError("INCOMPATIBLE_DAILY_MANIFEST")
    known = {}
    for record in manifest["files"]:
        relative = PurePosixPath(record["path"])
        path = root / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not path.resolve().is_relative_to(root)
            or path.is_symlink()
        ):
            raise ValueError("INVALID_MANIFEST_PATH")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError("DATASET_HASH_MISMATCH")
        known[relative.as_posix()] = path
    closes = {}
    selected = products if products is not None else spec["products"]
    if (
        not selected
        or len(selected) != len(set(selected))
        or not set(selected) <= set(spec["products"])
    ):
        raise ValueError("INVALID_PRODUCT_SUBSET")
    for product in selected:
        key = f"normalized/{product}.csv"
        if key not in known:
            raise ValueError("PRODUCT_COVERAGE_MISSING")
        with known[key].open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len({r["date"] for r in rows}) != len(rows):
            raise ValueError("DUPLICATE_DAILY_BARS")
        for row in rows:
            date.fromisoformat(row["date"])
            opening, high, low, close, volume = (
                float(row[k]) for k in ("open", "high", "low", "close", "volume")
            )
            if (
                not all(math.isfinite(v) for v in (opening, high, low, close, volume))
                or min(opening, high, low, close) <= 0
                or volume < 0
                or not low <= min(opening, close) <= max(opening, close) <= high
            ):
                raise ValueError("INVALID_OHLCV")
        closes[product] = {r["date"]: float(r["close"]) for r in rows}
    common = sorted(set.intersection(*(set(v) for v in closes.values())))
    return {
        "dates": common,
        "close": {p: [closes[p][day] for day in common] for p in closes},
        "quote_currency": "USDT",
        "calendar": "365",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "universe_status": spec["universe_status"],
    }
