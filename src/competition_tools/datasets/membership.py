"""Explicit licensed membership intervals, without current-to-PIT inference."""

import csv
from datetime import date
from pathlib import Path


def load_membership(path: Path, *, status: str) -> list[dict]:
    if status not in {"fixed_current", "point_in_time"}:
        raise ValueError("INVALID_UNIVERSE_STATUS")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != {
            "stable_id",
            "symbol",
            "valid_from",
            "valid_to",
            "available_at",
        }:
            raise ValueError("INVALID_MEMBERSHIP_COLUMNS")
        records = list(reader)
    intervals = {}
    for record in records:
        start = date.fromisoformat(record["valid_from"])
        end = date.fromisoformat(record["valid_to"]) if record["valid_to"] else date.max
        if not record["stable_id"] or not record["symbol"] or end < start:
            raise ValueError("INVALID_MEMBERSHIP_INTERVAL")
        if record["available_at"]:
            date.fromisoformat(record["available_at"])
        for old_start, old_end in intervals.setdefault(record["stable_id"], []):
            if start <= old_end and old_start <= end:
                raise ValueError("OVERLAPPING_MEMBERSHIP")
        intervals[record["stable_id"]].append((start, end))
        record["universe_status"] = status
    return records


def eligible(records: list[dict], session: str, as_of: str) -> list[dict]:
    day, cutoff = date.fromisoformat(session), date.fromisoformat(as_of)
    return [
        r
        for r in records
        if r["universe_status"] == "point_in_time"
        and r["available_at"]
        and date.fromisoformat(r["available_at"]) <= cutoff
        and date.fromisoformat(r["valid_from"]) <= day
        and (not r["valid_to"] or day <= date.fromisoformat(r["valid_to"]))
    ]
