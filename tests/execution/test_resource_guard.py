from pathlib import Path

import pytest

from apps.execution_runner.resources import ResourceBudget, RunLock


def test_resource_budget_is_windows_safe_by_default():
    budget = ResourceBudget()
    assert budget.max_workers == 2
    assert budget.max_memory_gb == 8.0


def test_run_lock_prevents_two_simultaneous_runs(tmp_path: Path):
    first = RunLock(tmp_path / "runner.lock")
    second = RunLock(tmp_path / "runner.lock")
    first.acquire()
    with pytest.raises(RuntimeError, match="already held"):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
