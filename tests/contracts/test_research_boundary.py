"""Research reports cannot be interpreted as execution instructions."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from packages.contracts import TargetSet, TargetValidationError


@pytest.mark.parametrize("payload", [
    {"strategy": "equal_weight", "run_status": "completed", "metrics": {}},
    {"synthetic": True, "files": []},
    {"strategy_id": "B0", "total_pnl": 0.0},
])
def test_research_artifact_is_not_execution_handoff(payload):
    with pytest.raises(TargetValidationError):
        TargetSet.from_dict(payload)


@pytest.mark.parametrize("market", ["HK", "CRYPTO"])
def test_research_does_not_expand_execution_markets(market):
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/targets.schema.json").read_text())
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({"schema_version": "1.0", "strategy_id": "demo",
                             "market": market, "as_of": "2026-01-01T00:00:00Z",
                             "targets": [{"symbol": "HK.DEMO_A", "weight": "1"}]})
