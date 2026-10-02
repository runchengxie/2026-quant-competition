from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.execution_runner.config import RunnerSettings
from apps.execution_runner.runner import ExecutionRunner
from packages.contracts import TargetManifestV2, TargetSet, TargetValidationError
from packages.market_model import Market
from strategies.nira.handoff import HandoffValidationError, NiraTargetHandoff


def payload():
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/targets.v2.valid.json").read_text()
    )


@pytest.mark.parametrize("method", ["run", "run_rebalance"])
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("kind", ["v2", "duck", "wrong_version_v1"])
def test_runner_rejects_non_v1_before_inspection_or_side_effects(
    tmp_path, method, dry_run, kind
):
    if kind == "v2":
        value = TargetManifestV2.from_dict(payload())
    elif kind == "duck":
        value = SimpleNamespace(
            targets=(
                SimpleNamespace(
                    symbol="TEST.US", weight=Decimal("0.1"), quantity=Decimal("1")
                ),
            )
        )
    else:
        value = replace(
            TargetSet("1.0", "test", Market.US, datetime(2026, 10, 2, tzinfo=UTC), ()),
            schema_version="2.0",
        )
    port = Mock()
    journal = tmp_path / "events.jsonl"
    runner = ExecutionRunner(
        RunnerSettings(dry_run=dry_run), submission_port=port, journal_path=journal
    )
    with pytest.raises(
        TargetValidationError, match="execution requires a v1 TargetSet"
    ):
        if method == "run":
            runner.run(value)
        else:
            runner.run_rebalance(value, {})
    assert port.mock_calls == []
    assert not journal.exists()


def test_nira_wire_handoff_rejects_v2_manifest():
    with pytest.raises(HandoffValidationError):
        NiraTargetHandoff.from_payload(payload())
