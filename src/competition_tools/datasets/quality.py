"""Daily-bar validation and inspectable dataset coverage."""

import math
from datetime import date
from pathlib import Path


def validate_bars(rows: list[list[str]]) -> None:
    seen = set()
    previous = None
    for row in rows:
        if len(row) != 6:
            raise ValueError("INVALID_BAR_SHAPE")
        day = date.fromisoformat(row[0])
        if day in seen or (previous is not None and day <= previous):
            raise ValueError("DUPLICATE_OR_UNSORTED_BAR")
        seen.add(day)
        previous = day
        opening, high, low, close, volume = map(float, row[1:])
        if not all(math.isfinite(x) for x in (opening, high, low, close, volume)):
            raise ValueError("NONFINITE_BAR")
        if (
            min(opening, high, low, close) <= 0
            or volume < 0
            or not low <= min(opening, close) <= max(opening, close) <= high
        ):
            raise ValueError("INVALID_OHLCV")


def inspect_dataset(manifest_path: Path) -> dict:
    from .storage import verify_manifest

    manifest = verify_manifest(manifest_path)
    return {
        "schema": "competition.coverage_report.v2" if manifest["schema"] == "competition.dataset_manifest.v2" else "competition.coverage_report.v1",
        "dataset_id": manifest["dataset_id"],
        "version": manifest["version"],
        "status": manifest["status"],
        "coverage": manifest["coverage"],
        "gaps": manifest["gaps"],
        "universe_status": manifest["spec"]["universe_status"],
        "accepted_research": False,
    }
