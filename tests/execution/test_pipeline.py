import json
import pytest

from apps.execution_runner.pipeline import run_target_pipeline
from apps.execution_runner.config import RunnerSettings
from apps.execution_runner.safety import KillSwitch


def test_target_pipeline_runs_end_to_end_without_broker_side_effect(tmp_path):
    target = tmp_path / "targets.json"
    target.write_text(json.dumps({
        "schema_version":"1.0", "strategy_id":"japan-lite", "market":"JP",
        "as_of":"2026-09-03T00:00:00Z",
        "targets":[{"symbol":"1321.T","weight":"1.0","quantity":"1"}],
    }))
    result = run_target_pipeline(target, RunnerSettings(dry_run=True), journal_path=tmp_path / "events.jsonl")
    assert result.status == "dry_run"
    assert result.submitted is False


def test_pipeline_kill_switch_blocks_submission(tmp_path):
    target = tmp_path / "targets.json"
    target.write_text(json.dumps({
        "schema_version":"1.0", "strategy_id":"japan-lite", "market":"JP",
        "as_of":"2026-09-03T00:00:00Z",
        "targets":[{"symbol":"1321.T","weight":"1.0","quantity":"1"}],
    }))
    switch = KillSwitch(tmp_path / "STOP")
    switch.trigger("test")
    class RecordingPort:
        def submit(self, candidates):
            raise AssertionError("kill switch should block before submission")
    with pytest.raises(RuntimeError, match="kill switch"):
        run_target_pipeline(
            target, RunnerSettings(),
            journal_path=tmp_path / "events.jsonl", submission_port=RecordingPort(), kill_switch=switch,
        )
