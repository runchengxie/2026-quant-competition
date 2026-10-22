import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from competition_tools.datasets.dex_spec import validate_dex_spec, dataset_identity
from competition_tools.datasets.spec import load_spec
from competition_tools.datasets.dex_spec import safe_path


def test_empty_ancestor_git_placeholder_is_not_a_repository(tmp_path):
    (tmp_path / ".git").mkdir()
    assert (
        safe_path(tmp_path / "config/provider.env") == tmp_path / "config/provider.env"
    )
    (tmp_path / ".git/HEAD").write_text("ref: refs/heads/main\n")
    with pytest.raises(ValueError, match="Source repository"):
        safe_path(tmp_path / "config/provider.env")


def sample(tmp_path):
    return {
        "schema": "competition.dex_dataset_spec.v1",
        "dataset_id": "dex-pilot",
        "version": "v1",
        "source": "dexpaprika",
        "interval": "1h",
        "quote_currency": "USD",
        "selection": "fixed_current",
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-04-01T00:00:00Z",
        "credential_file": str(tmp_path / "provider.env"),
        "protocol_file": str(tmp_path / "protocol.json"),
        "protocol_sha256": "a" * 64,
        "assets": [
            {
                "stable_id": "wrapped-sol",
                "underlying_id": "sol",
                "network": "solana",
                "address": "So11111111111111111111111111111111111111112",
            }
        ],
        "budget": {
            "requests": 100,
            "bytes": 52428800,
            "seconds": 900,
            "requests_per_minute": 20,
        },
    }


def test_hour_grid_is_not_daily_contract(tmp_path):
    value = sample(tmp_path)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(value))
    assert load_spec(path) == value
    schema = json.loads(
        (
            Path(__file__).parents[2]
            / "schemas/research/dex-dataset-spec.v1.schema.json"
        ).read_text()
    )
    Draft202012Validator(schema).validate(value)
    assert "credential_file" not in dataset_identity(value)
    assert "protocol_sha256" not in dataset_identity(value)


def test_solana_case_is_preserved(tmp_path):
    value = sample(tmp_path)
    original = copy.deepcopy(value)
    validate_dex_spec(value)
    assert value == original


def test_duplicate_underlying_is_rejected(tmp_path):
    value = sample(tmp_path)
    value["assets"].append(
        {
            "stable_id": "sol-copy",
            "underlying_id": "sol",
            "network": "ethereum",
            "address": "0x" + "1" * 40,
        }
    )
    with pytest.raises(ValueError):
        validate_dex_spec(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("requests", True),
        ("requests", 101),
        ("bytes", 52428801),
        ("seconds", 901),
        ("requests_per_minute", 21),
        ("requests", 0),
    ],
)
def test_budget_boundaries(tmp_path, field, value):
    spec = sample(tmp_path)
    spec["budget"][field] = value
    with pytest.raises(ValueError):
        validate_dex_spec(spec)


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(extra=1),
        lambda v: v.update(end="2025-04-01T00:30:00Z"),
        lambda v: v.update(end="2099-04-01T00:00:00Z"),
        lambda v: v.update(start="2025-01-02T00:00:00Z"),
        lambda v: v["assets"][0].update(network="Solana"),
        lambda v: v["assets"][0].update(address="../bad"),
        lambda v: v.update(protocol_sha256="x"),
        lambda v: v.update(credential_file="relative.env"),
    ],
)
def test_unknown_fields_and_invalid_grid(tmp_path, change):
    value = sample(tmp_path)
    change(value)
    with pytest.raises(ValueError):
        validate_dex_spec(value)
