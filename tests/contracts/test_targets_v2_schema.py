import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from packages.contracts import TargetManifestV2, TargetValidationError


ROOT = Path(__file__).parents[2]


@pytest.fixture
def payload():
    return json.loads((ROOT / "tests/fixtures/targets.v2.valid.json").read_text())


@pytest.fixture
def validator():
    schema = json.loads((ROOT / "schemas/targets.v2.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema, format_checker=FormatChecker(formats=["date", "date-time"])
    )


def test_valid_manifest_and_serialized_output_satisfy_schema(validator, payload):
    validator.validate(payload)
    validator.validate(TargetManifestV2.from_dict(payload).to_dict())


@pytest.mark.parametrize(
    "path,value",
    [
        ("schema_version", "3.0"),
        ("strategy_id", " "),
        ("targets", []),
        ("reporting_currency", "usd"),
        ("as_of", "2026-10-02T08:00:00+08:00"),
        ("as_of", "2026-02-30T08:00:00Z"),
        ("targets.0.weight", 0.3),
        ("targets.0.weight", "1.1"),
        ("targets.0.quantity", "0.0"),
        ("targets.0.instrument.unexpected", True),
        ("targets.1.instrument.currency", "JP"),
        ("targets.2.quantity", "0"),
        ("targets.2.quantity", "1.5"),
        ("targets.2.quantity", 2),
        ("targets.2.instrument.exchange_mic", "CME"),
        ("targets.2.instrument.contract_month", "202613"),
        ("targets.2.instrument.contract_month", "000012"),
        ("targets.2.instrument.expiry_date", "2026-02-30"),
        ("targets.2.instrument.multiplier", "0"),
        ("targets.2.instrument.tick_size", "0.0"),
    ],
)
def test_schema_and_python_reject_same_wire_errors(validator, payload, path, value):
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    current[parts[-1]] = value
    assert list(validator.iter_errors(payload))
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    [
        "contract_month",
        "expiry_date",
        "multiplier",
        "tick_size",
        "roll_rule_id",
        "settlement_type",
        "margin_model_id",
    ],
)
def test_schema_and_python_require_future_metadata(validator, payload, field):
    del payload["targets"][2]["instrument"][field]
    assert list(validator.iter_errors(payload))
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


def test_schema_and_python_require_future_quantity(validator, payload):
    del payload["targets"][2]["quantity"]
    assert list(validator.iter_errors(payload))
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


def test_integral_decimal_quantity_is_valid_in_both(validator, payload):
    payload["targets"][2]["quantity"] = "002.00"
    validator.validate(payload)
    TargetManifestV2.from_dict(payload)


def test_semantic_overallocation_requires_python_validation(validator, payload):
    payload["targets"][0]["weight"] = "0.9"
    validator.validate(payload)
    with pytest.raises(TargetValidationError, match="sum of weights"):
        TargetManifestV2.from_dict(payload)


def test_more_than_microsecond_timestamp_rejected_in_both(validator, payload):
    payload["as_of"] = "2026-10-02T08:00:00.123456789Z"
    assert list(validator.iter_errors(payload))
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


@pytest.mark.parametrize(
    "path,value",
    [
        ("reporting_currency", "USD\n"),
        ("targets.0.weight", "0.3\n"),
        ("targets.0.quantity", "100\n"),
        ("targets.0.instrument.market", "US\n"),
        ("targets.0.instrument.exchange_mic", "XNYS\n"),
        ("targets.2.quantity", "2\n"),
        ("targets.2.instrument.contract_month", "202612\n"),
    ],
)
def test_schema_and_python_reject_trailing_newline(validator, payload, path, value):
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    current[parts[-1]] = value
    assert list(validator.iter_errors(payload))
    with pytest.raises(TargetValidationError):
        TargetManifestV2.from_dict(payload)


def test_microseconds_and_utc_offset_roundtrip(validator, payload):
    payload["as_of"] = "2026-10-02T08:00:00.123456+00:00"
    validator.validate(payload)
    result = TargetManifestV2.from_dict(payload).to_dict()
    assert result["as_of"] == "2026-10-02T08:00:00.123456Z"
    validator.validate(result)
