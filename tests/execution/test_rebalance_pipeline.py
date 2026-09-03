from decimal import Decimal
import json

from apps.execution_runner.config import RunnerSettings
from apps.execution_runner.pipeline import run_target_rebalance_pipeline


def test_rebalance_pipeline_plans_against_current_positions(tmp_path):
    targets = {
        "schema_version": "1.0", "strategy_id": "japanese-nira", "market": "JP",
        "as_of": "2026-09-03T00:00:00Z",
        "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "2"}],
    }
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(targets), encoding="utf-8")

    result = run_target_rebalance_pipeline(
        path, RunnerSettings(dry_run=True),
        positions={"1321.T": Decimal("1")},
        journal_path=tmp_path / "events.jsonl",
    )

    assert result.status == "dry_run"
    assert result.intents[0].side == "BUY"
    assert result.intents[0].quantity == Decimal("1")
