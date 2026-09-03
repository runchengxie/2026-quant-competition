"""Small, dependency-free alignment audit for Nira signal artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


@dataclass(frozen=True, slots=True)
class AlignmentAudit:
    signal_count: int
    return_count: int
    aligned_count: int
    future_overlap_count: int
    first_signal: str | None
    last_signal: str | None

    @property
    def passed(self) -> bool:
        return self.future_overlap_count == 0 and self.aligned_count > 0


def audit_forward_alignment(
    signal_dates: Iterable[date | datetime | str],
    return_dates: Iterable[date | datetime | str],
    *,
    horizon: int = 1,
) -> AlignmentAudit:
    """Check that each signal is evaluated only against a future return date.

    This is deliberately a date-level audit. It catches same-day and backward
    joins, but does not prove feature construction itself is leakage-free.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    signals = sorted({_as_date(value) for value in signal_dates})
    returns = sorted({_as_date(value) for value in return_dates})
    pairs = min(len(signals), max(0, len(returns) - horizon + 1))
    future_overlap = sum(
        1 for index in range(pairs) if returns[index + horizon - 1] <= signals[index]
    )
    aligned = pairs - future_overlap
    return AlignmentAudit(
        signal_count=len(signals), return_count=len(returns), aligned_count=aligned,
        future_overlap_count=future_overlap, first_signal=_fmt(signals[0] if signals else None),
        last_signal=_fmt(signals[-1] if signals else None),
    )


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _fmt(value: date | None) -> str | None:
    return value.isoformat() if value else None
