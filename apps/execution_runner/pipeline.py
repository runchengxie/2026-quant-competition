from __future__ import annotations

from pathlib import Path

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
