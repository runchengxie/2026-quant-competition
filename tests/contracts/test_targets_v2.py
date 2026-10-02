import copy
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest

from packages.contracts import (
    FuturesInstrumentV2,
    SecurityInstrumentV2,
    TargetManifestV2,
    TargetSet,
    TargetValidationError,
)


@pytest.fixture
def payload():
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/targets.v2.valid.json").read_text()
    )


def test_mixed_manifest_round_trips_without_losing_decimal_precision(payload):
    payload["targets"][2]["instrument"]["tick_size"] = "0.00000000000000000001"
    manifest = TargetManifestV2.from_dict(payload)
    assert isinstance(manifest.targets[0].instrument, SecurityInstrumentV2)
    assert isinstance(manifest.targets[2].instrument, FuturesInstrumentV2)
    assert manifest.targets[2].instrument.tick_size == Decimal("0.00000000000000000001")
    assert manifest.as_of == datetime(2026, 10, 2, 8, tzinfo=UTC)
    wire = json.loads(json.dumps(manifest.to_dict()))
    assert "market" not in wire
    assert TargetManifestV2.from_dict(wire) == manifest


def test_v1_reader_rejects_v2(payload):
    with pytest.raises(TargetValidationError):
        TargetSet.from_dict(payload)


@pytest.mark.parametrize("container", [None, [], "text", 1, True])
def test_non_object_root_rejected(container):
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(container)


@pytest.mark.parametrize(
    "field", ["schema_version", "strategy_id", "as_of", "reporting_currency", "targets"]
)
def test_missing_root_fields_rejected(payload, field):
    del payload[field]
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "3.0"),
        ("strategy_id", " "),
        ("targets", []),
        ("targets", {}),
        ("targets", [None]),
        ("reporting_currency", "usd"),
        ("reporting_currency", "US"),
        ("reporting_currency", 123),
        ("as_of", "2026-10-02T08:00:00"),
        ("as_of", "2026-10-02T08:00:00+08:00"),
        ("as_of", "2026-02-30T08:00:00Z"),
        ("as_of", "20261002T080000Z"),
    ],
)
def test_bad_root_values_rejected(payload, field, value):
    payload[field] = value
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    [
        "asset_type",
        "symbol",
        "market",
        "exchange_mic",
        "currency",
        "contract_month",
        "expiry_date",
        "multiplier",
        "tick_size",
        "roll_rule_id",
        "settlement_type",
        "margin_model_id",
    ],
)
def test_missing_future_metadata_rejected(payload, field):
    del payload["targets"][2]["instrument"][field]
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("asset_type", "option"),
        ("symbol", " "),
        ("market", "us"),
        ("market", ","),
        ("exchange_mic", "cme"),
        ("exchange_mic", "ABCDE"),
        ("currency", "usd"),
        ("currency", "USD "),
        ("contract_month", "202600"),
        ("contract_month", "202613"),
        ("contract_month", "000012"),
        ("contract_month", "2026-12"),
        ("contract_month", 202612),
        ("expiry_date", "2026-02-30"),
        ("expiry_date", "2026-10-02"),
        ("expiry_date", "2026-10-01"),
        ("expiry_date", "20261218"),
        ("multiplier", "0"),
        ("tick_size", "0.0"),
        ("tick_size", "NaN"),
        ("tick_size", "-0.1"),
        ("multiplier", 50),
        ("multiplier", True),
        ("roll_rule_id", " "),
        ("margin_model_id", ""),
        ("settlement_type", "unknown"),
    ],
)
def test_bad_future_metadata_rejected(payload, field, value):
    payload["targets"][2]["instrument"][field] = value
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("weight", 0.1),
        ("weight", True),
        ("weight", "1.1"),
        ("weight", "-0.1"),
        ("weight", "NaN"),
        ("quantity", "0"),
        ("quantity", "2.1"),
        ("quantity", None),
        ("quantity", 2),
        ("instrument", []),
    ],
)
def test_bad_future_target_fields_rejected(payload, field, value):
    payload["targets"][2][field] = value
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


def test_missing_future_quantity_rejected(payload):
    del payload["targets"][2]["quantity"]
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize("level", ["root", "target", "instrument"])
def test_unknown_fields_rejected(payload, level):
    container = {
        "root": payload,
        "target": payload["targets"][0],
        "instrument": payload["targets"][0]["instrument"],
    }[level]
    container["unexpected"] = True
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize("index", [0, 2])
def test_duplicate_identity_rejected_even_if_metadata_conflicts(payload, index):
    duplicate = copy.deepcopy(payload["targets"][index])
    if index == 2:
        duplicate["instrument"]["multiplier"] = "100"
    payload["targets"].append(duplicate)
    with pytest.raises(TargetValidationError, match="duplicate"):
        TargetManifestV2.from_dict(payload)


def test_different_contract_months_are_distinct(payload):
    other = copy.deepcopy(payload["targets"][2])
    other["instrument"].update(contract_month="202703", expiry_date="2027-03-19")
    payload["targets"].append(other)
    assert len(TargetManifestV2.from_dict(payload).targets) == 4


def test_overallocated_manifest_rejected(payload):
    payload["targets"][0]["weight"] = "0.9"
    with pytest.raises(TargetValidationError, match="sum of weights"):
        TargetManifestV2.from_dict(payload)


def test_integral_decimal_contract_count_accepted(payload):
    payload["targets"][2]["quantity"] = "2.00"
    assert TargetManifestV2.from_dict(payload).targets[2].quantity == Decimal("2")


def test_tiny_overallocation_rejected_without_decimal_context_rounding(payload):
    payload["targets"][0]["weight"] = "0.99999999999999999999999999999"
    payload["targets"][1]["weight"] = "0.00000000000000000000000000002"
    payload["targets"][2]["weight"] = "0"
    with pytest.raises(TargetValidationError, match="sum of weights"):
        TargetManifestV2.from_dict(payload)
