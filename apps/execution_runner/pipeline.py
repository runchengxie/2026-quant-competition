from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from decimal import Decimal

from strategies.nira.handoff import load_target_artifact

from .config import RunnerSettings
from .runner import ExecutionRunResult, ExecutionRunner, SubmissionPort
from .safety import KillSwitch


def run_target_pipeline(
    targets_path: str | Path,
    settings: RunnerSettings,
    *,
    journal_path: str | Path,
    submission_port: SubmissionPort | None = None,
    kill_switch: KillSwitch | None = None,
) -> ExecutionRunResult:
    """Validate an external target, run it, and persist facts through the runner."""
    handoff = load_target_artifact(targets_path)
    runner = ExecutionRunner(
        settings,
        submission_port=submission_port,
        journal_path=journal_path,
        run_id=handoff.lineage.get("research_run_id"),
        kill_switch=kill_switch,
    )
    return runner.run(handoff.target_set)


def run_target_rebalance_pipeline(
    targets_path: str | Path,
    settings: RunnerSettings,
    *,
    positions: Mapping[str, Decimal],
    journal_path: str | Path,
    submission_port: SubmissionPort | None = None,
    kill_switch: KillSwitch | None = None,
) -> ExecutionRunResult:
    """Validate targets, plan position deltas, and run Paper-safe execution."""
    handoff = load_target_artifact(targets_path)
    runner = ExecutionRunner(
        settings,
        submission_port=submission_port,
        journal_path=journal_path,
        run_id=handoff.lineage.get("research_run_id"),
        kill_switch=kill_switch,
    )
    return runner.run_rebalance(handoff.target_set, positions)
