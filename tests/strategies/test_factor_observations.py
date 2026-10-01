from datetime import datetime, timezone
from math import nan

import pytest

from strategies.international_lite.factors import (
    FactorObservation,
    eligible_observation,
    ensure_unique_observations,
)


def observation(**overrides: object) -> FactorObservation:
    values: dict[str, object] = {
        "provider": "quantzone",
        "symbol": "600000.SH",
        "factor_id": "momentum_20d",
        "period_end": "2026-09-30",
        "available_at": "2026-10-01T01:00:00+00:00",
        "retrieved_at": "2026-10-01T01:05:00+00:00",
        "value": 0.12,
        "source_version": "snapshot-1",
    }
    values.update(overrides)
    return FactorObservation(**values)  # type: ignore[arg-type]


def test_observation_is_eligible_at_or_after_availability_cutoff() -> None:
    item = observation()
    cutoff = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)

    assert eligible_observation(item, decision_cutoff=cutoff)


def test_later_historical_retrieval_does_not_change_provider_availability_time() -> None:
    item = observation(retrieved_at="2026-10-02T01:05:00+00:00")
    cutoff = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)

    assert eligible_observation(item, decision_cutoff=cutoff)


def test_observation_published_after_cutoff_is_ineligible() -> None:
    item = observation()
    cutoff = datetime(2026, 10, 1, 0, 59, tzinfo=timezone.utc)

    assert not eligible_observation(item, decision_cutoff=cutoff)


@pytest.mark.parametrize(
    "field,value",
    [
        ("available_at", None),
        ("available_at", "2026-10-01T01:00:00"),
        ("retrieved_at", "2026-10-01T01:05:00"),
        ("value", nan),
        ("value", float("inf")),
    ],
)
def test_missing_naive_or_non_finite_observation_is_ineligible(field: str, value: object) -> None:
    item = observation(**{field: value})
    cutoff = datetime(2026, 10, 2, tzinfo=timezone.utc)

    assert not eligible_observation(item, decision_cutoff=cutoff)


def test_duplicate_observation_key_is_rejected_even_when_values_match() -> None:
    item = observation()

    with pytest.raises(ValueError, match="duplicate factor observation key"):
        ensure_unique_observations([item, item])


def test_conflicting_observation_version_is_rejected() -> None:
    first = observation()
    second = observation(value=0.13)

    with pytest.raises(ValueError, match="duplicate factor observation key"):
        ensure_unique_observations([first, second])
