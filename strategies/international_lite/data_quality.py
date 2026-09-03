from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ContinuityReport:
    row_count: int
    max_gap_days: int
    passed: bool


def check_daily_continuity(dates: Iterable[str], *, max_gap_days: int = 5) -> ContinuityReport:
    parsed = [date.fromisoformat(value) for value in dates]
    if len(parsed) != len(set(parsed)):
        raise ValueError("daily data contains duplicate dates")
    ordered = sorted(parsed)
    gaps = [(right - left).days for left, right in zip(ordered, ordered[1:])]
    maximum = max(gaps, default=0)
    return ContinuityReport(len(parsed), maximum, maximum <= max_gap_days)
