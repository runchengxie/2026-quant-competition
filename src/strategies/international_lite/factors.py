from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


@dataclass(frozen=True, slots=True)
class FactorDefinition:
    provider: str
    factor_id: str
    name: str
    formula_version: str
    asset_scope: str
    market_scope: str
    license_status: str
    validated_markets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FactorObservation:
    provider: str
    symbol: str
    factor_id: str
    period_end: str
    available_at: str | None
    retrieved_at: str | None
    value: float
    source_version: str


def factor_eligibility(
    definition: FactorDefinition, *, market: str, purpose: str
) -> tuple[bool, tuple[str, ...]]:
    """Fail closed unless metadata, rights, scope, and local validation are present."""
    if purpose not in {"research", "public_summary"}:
        raise ValueError(f"unknown factor purpose: {purpose}")

    reasons: list[str] = []
    if not definition.formula_version.strip():
        reasons.append("missing_formula_version")
    if not definition.market_scope.strip():
        reasons.append("missing_market_scope")

    permitted = {
        "confirmed_research": {"research"},
        "confirmed_research_and_publication": {"research", "public_summary"},
    }
    if purpose not in permitted.get(definition.license_status, set()):
        reason = (
            "publication_rights_unconfirmed"
            if purpose == "public_summary"
            and definition.license_status == "confirmed_research"
            else "license_unverified"
        )
        reasons.append(reason)

    market_code = market.upper()
    market_scope = {entry.strip().upper() for entry in definition.market_scope.split(",") if entry.strip()}
    if market_scope and market_code not in market_scope:
        reasons.append("market_scope_mismatch")
    elif market_code not in {entry.upper() for entry in definition.validated_markets}:
        reasons.append("market_not_validated")

    return not reasons, tuple(reasons)


def _parse_aware_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def eligible_observation(
    observation: FactorObservation, *, decision_cutoff: datetime
) -> bool:
    """Return whether the observation was available for the specified decision."""
    if decision_cutoff.tzinfo is None or decision_cutoff.utcoffset() is None:
        return False
    available_at = _parse_aware_datetime(observation.available_at)
    retrieved_at = _parse_aware_datetime(observation.retrieved_at)
    if available_at is None or retrieved_at is None or not isfinite(observation.value):
        return False
    return available_at <= decision_cutoff


def ensure_unique_observations(observations: Iterable[FactorObservation]) -> None:
    """Reject duplicate provider snapshot keys, including identical duplicates."""
    seen: set[tuple[str, str, str, str, str]] = set()
    for observation in observations:
        key = (
            observation.provider,
            observation.factor_id,
            observation.symbol,
            observation.period_end,
            observation.source_version,
        )
        if key in seen:
            raise ValueError(f"duplicate factor observation key: {key!r}")
        seen.add(key)
