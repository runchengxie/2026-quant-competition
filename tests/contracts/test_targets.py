from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.contracts import TargetSet, TargetValidationError


def valid_payload() -> dict:
    return {
        "schema_version": "1.0",
        "strategy_id": "japanese-nira",
        "market": "JP",
        "as_of": "2026-09-03T00:00:00Z",
        "targets": [
            {"symbol": "7203.T", "weight": "0.60", "quantity": "100"},
            {"symbol": "1321.T", "weight": "0.20", "quantity": "1"},
        ],
    }


def test_target_set_parses_stable_decimal_fields_and_utc_timestamp() -> None:
    target_set = TargetSet.from_dict(valid_payload())

    assert target_set.strategy_id == "japanese-nira"
    assert target_set.as_of == datetime(2026, 9, 3, tzinfo=UTC)
    assert target_set.targets[0].weight == Decimal("0.60")
    assert target_set.targets[0].quantity == Decimal("100")


def test_target_set_rejects_duplicate_symbols() -> None:
    payload = valid_payload()
    payload["targets"].append({"symbol": "7203.T", "weight": "0.1"})

    with pytest.raises(TargetValidationError, match="duplicate symbol"):
        TargetSet.from_dict(payload)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("as_of", "2026-09-03T00:00:00", "UTC"),
        ("targets", [], "at least one target"),
        ("market", "US", "market"),
    ],
)
def test_target_set_rejects_invalid_required_values(
    field: str, value: object, message: str
) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(TargetValidationError, match=message):
        TargetSet.from_dict(payload)


def test_target_set_rejects_target_outside_market_and_invalid_weight() -> None:
    payload = valid_payload()
    payload["targets"] = [{"symbol": "AAPL.US", "weight": "1.01"}]

    with pytest.raises(TargetValidationError, match="market|weight"):
        TargetSet.from_dict(payload)


def test_target_set_rejects_non_lot_quantity() -> None:
    payload = valid_payload()
    payload["targets"] = [{"symbol": "7203.T", "weight": "0.5", "quantity": "99"}]

    with pytest.raises(TargetValidationError, match="lot"):
        TargetSet.from_dict(payload)


def test_target_set_rejects_over_allocated_weights() -> None:
    payload = valid_payload()
    payload["targets"] = [
        {"symbol": "7203.T", "weight": "0.70"},
        {"symbol": "1321.T", "weight": "0.70"},
    ]

    with pytest.raises(TargetValidationError, match="sum of weights"):
        TargetSet.from_dict(payload)


@pytest.mark.parametrize(
    "payload_update, message",
    [
        ({"unexpected": "value"}, "unknown root field"),
        ({"targets": [{"symbol": "7203.T", "weight": "0.5", "oops": True}]}, "unknown target field"),
    ],
)
def test_target_set_rejects_unknown_wire_fields(
    payload_update: dict[str, object], message: str
) -> None:
    payload = valid_payload()
    payload.update(payload_update)

    with pytest.raises(TargetValidationError, match=message):
        TargetSet.from_dict(payload)


@pytest.mark.parametrize("field", ["weight", "quantity"])
def test_target_set_rejects_numeric_decimal_wire_values(field: str) -> None:
    payload = valid_payload()
    payload["targets"] = [{"symbol": "1321.T", "weight": "0.5", "quantity": "1"}]
    payload["targets"][0][field] = 1

    with pytest.raises(TargetValidationError, match=f"{field} must be a decimal string"):
        TargetSet.from_dict(payload)


def test_target_set_to_dict_round_trips_through_json_loader() -> None:
    import json

    original = TargetSet.from_dict(valid_payload())
    wire_payload = json.loads(json.dumps(original.to_dict()))

    assert TargetSet.from_dict(wire_payload) == original
