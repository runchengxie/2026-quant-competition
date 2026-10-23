"""Daily final-volume diagnostics; never feed these values into policy decisions."""

import csv
import math
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.quality import validate_bars
from ...datasets.storage import digest


def load_volumes(job: dict, dates: list[str]) -> dict:
    base = job["input_job"]
    manifest = safe_path(Path(base["manifest"]))
    if digest(manifest) != base["manifest_sha256"]:
        raise ValueError("CAPACITY_MANIFEST_CHANGED")
    lookup = {r["path"]: r for r in base["input_files"]}
    volumes = {}
    for product in job["products"]:
        relative = f"normalized/{product}.csv"
        record = lookup[relative]
        path = safe_path(manifest.parent / relative)
        if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise ValueError("CAPACITY_INPUT_CHANGED")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_CAPACITY_HEADER")
            rows = list(reader)
        validate_bars(rows)
        by_date = {r[0]: float(r[5]) for r in rows}
        volumes[product] = [by_date.get(d) for d in dates]
    return volumes


def capacity_diagnostics(job: dict, periods: dict, volumes: dict | None) -> dict:
    if job["market"] != "crypto":
        raise ValueError("CRYPTO_CAPACITY_ONLY")
    prices = periods["prices"]
    dates, closes = prices["dates"], prices["close"]
    products = job["products"]
    if len(periods["net"]) != len(dates) - 1 or set(closes) != set(products):
        raise ValueError("INVALID_CAPACITY_GRID")
    volumes = load_volumes(job, dates) if volumes is None else volumes
    previous = {p: 0.0 for p in products}
    before, trades = 1.0, []
    for i, period in enumerate(periods["net"]):
        quantities = {p: period["positions"][p] / closes[p][i + 1] for p in products}
        changes = {p: abs(quantities[p] - previous[p]) for p in products}
        value = sum(changes[p] * closes[p][i] for p in products)
        if not math.isfinite(value) or not math.isclose(
            value, period["turnover"] * before, abs_tol=1e-10, rel_tol=1e-10
        ):
            raise ValueError("CAPACITY_TURNOVER_MISMATCH")
        trades.append(changes)
        previous, before = quantities, period["equity"]
    checks = []
    for notional in (10000, 100000, 1000000):
        ratios, missing = [], 0
        for i, changes in enumerate(trades):
            day_ratios, unavailable = [], False
            for p, change in changes.items():
                if change < 1e-12:
                    continue
                available = volumes.get(p, [])
                volume = available[i] if i < len(available) else None
                if (
                    type(volume) not in (int, float)
                    or not math.isfinite(volume)
                    or volume <= 0
                ):
                    unavailable = True
                else:
                    day_ratios.append(change * notional / volume)
            if unavailable:
                missing += 1
            ratios.append(max(day_ratios, default=0.0) if not unavailable else None)
        for threshold in (0.01, 0.05):
            checks.append(
                dict(
                    job_id=job["job_id"],
                    notional_usdt=notional,
                    threshold=threshold,
                    status="incomplete_volume" if missing else "diagnostic_only",
                    max_participation=max(
                        (r for r in ratios if r is not None), default=None
                    ),
                    breach_days=sum(r is not None and r > threshold for r in ratios),
                    unavailable_days=missing,
                    ex_post=True,
                    execution_eligible=False,
                )
            )
    return dict(schema="competition.strategy_robustness_capacity.v1", checks=checks)
