from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

RESEARCH_CLOCK_SCHEMA_VERSION = "research.clock.v1"


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _aware_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _required_text(value, field)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _optional_aware_datetime(value: object, field: str) -> datetime | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _aware_datetime(value, field)


def _after(left: datetime, right: datetime) -> bool:
    return left.astimezone(UTC) > right.astimezone(UTC)


@dataclass(frozen=True)
class ResearchClock:
    timezone: str
    information_cutoff_at: datetime
    signal_at: datetime
    decision_at: datetime
    valuation_at: datetime
    timing_policy_id: str
    trading_calendar_ref: str
    earliest_order_at: datetime | None = None
    execution_window_start_at: datetime | None = None
    execution_window_end_at: datetime | None = None
    schema_version: str = RESEARCH_CLOCK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESEARCH_CLOCK_SCHEMA_VERSION:
            raise ValueError(f"unsupported research clock schema {self.schema_version!r}")
        _required_text(self.timezone, "timezone")
        _required_text(self.timing_policy_id, "timing_policy_id")
        _required_text(self.trading_calendar_ref, "trading_calendar_ref")
        _aware_datetime(self.information_cutoff_at, "information_cutoff_at")
        _aware_datetime(self.signal_at, "signal_at")
        _aware_datetime(self.decision_at, "decision_at")
        _aware_datetime(self.valuation_at, "valuation_at")
        if self.earliest_order_at is not None:
            _aware_datetime(self.earliest_order_at, "earliest_order_at")
        if self.execution_window_start_at is not None:
            _aware_datetime(self.execution_window_start_at, "execution_window_start_at")
        if self.execution_window_end_at is not None:
            _aware_datetime(self.execution_window_end_at, "execution_window_end_at")
        self._validate_ordering()

    def _validate_ordering(self) -> None:
        if _after(self.information_cutoff_at, self.signal_at):
            raise ValueError("information_cutoff_at must be <= signal_at")
        if _after(self.signal_at, self.decision_at):
            raise ValueError("signal_at must be <= decision_at")
        if _after(self.decision_at, self.valuation_at):
            raise ValueError("decision_at must be <= valuation_at")

        self._validate_execution_window()

    def _validate_execution_window(self) -> None:
        start = self.execution_window_start_at
        end = self.execution_window_end_at
        if (start is None) != (end is None):
            raise ValueError(
                "execution_window_start_at and execution_window_end_at must be provided together"
            )
        if self.earliest_order_at is not None and _after(self.decision_at, self.earliest_order_at):
            raise ValueError("decision_at must be <= earliest_order_at")
        if start is None or end is None:
            return

        if _after(self.decision_at, start):
            raise ValueError("decision_at must be <= execution_window_start_at")
        if _after(start, end):
            raise ValueError("execution_window_start_at must be <= execution_window_end_at")
        if self.earliest_order_at is not None and _after(self.earliest_order_at, end):
            raise ValueError("earliest_order_at must be <= execution_window_end_at")
        if _after(end, self.valuation_at):
            raise ValueError("execution_window_end_at must be <= valuation_at")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResearchClock:
        schema_version = _required_text(payload.get("schema_version"), "schema_version")
        if schema_version != RESEARCH_CLOCK_SCHEMA_VERSION:
            raise ValueError(f"unsupported research clock schema {schema_version!r}")
        return cls(
            schema_version=schema_version,
            timezone=_required_text(payload.get("timezone"), "timezone"),
            information_cutoff_at=_aware_datetime(
                payload.get("information_cutoff_at"), "information_cutoff_at"
            ),
            signal_at=_aware_datetime(payload.get("signal_at"), "signal_at"),
            decision_at=_aware_datetime(payload.get("decision_at"), "decision_at"),
            earliest_order_at=_optional_aware_datetime(
                payload.get("earliest_order_at"), "earliest_order_at"
            ),
            execution_window_start_at=_optional_aware_datetime(
                payload.get("execution_window_start_at"), "execution_window_start_at"
            ),
            execution_window_end_at=_optional_aware_datetime(
                payload.get("execution_window_end_at"), "execution_window_end_at"
            ),
            valuation_at=_aware_datetime(payload.get("valuation_at"), "valuation_at"),
            timing_policy_id=_required_text(payload.get("timing_policy_id"), "timing_policy_id"),
            trading_calendar_ref=_required_text(
                payload.get("trading_calendar_ref"), "trading_calendar_ref"
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "timezone": self.timezone,
            "information_cutoff_at": self.information_cutoff_at.isoformat(),
            "signal_at": self.signal_at.isoformat(),
            "decision_at": self.decision_at.isoformat(),
            "valuation_at": self.valuation_at.isoformat(),
            "timing_policy_id": self.timing_policy_id,
            "trading_calendar_ref": self.trading_calendar_ref,
        }
        for field in (
            "earliest_order_at",
            "execution_window_start_at",
            "execution_window_end_at",
        ):
            value = getattr(self, field)
            result[field] = value.isoformat() if value is not None else None
        return result


def validate_research_clock(
    payload: Mapping[str, Any], *, require_execution: bool = False
) -> ResearchClock:
    if require_execution:
        for field in (
            "earliest_order_at",
            "execution_window_start_at",
            "execution_window_end_at",
        ):
            value = payload.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(f"{field} is required for execution-aware research")
    return ResearchClock.from_mapping(payload)
