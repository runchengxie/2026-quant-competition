"""Synthetic timing records distinguish child state from outer deadlines."""

import json
import shutil

import pytest


@pytest.mark.parametrize(
    "started,code,observed,outer,want",
    [
        (False, None, False, False, "start_failed"),
        (True, 7, False, False, "child_failed"),
        (True, None, True, False, "observation_timeout"),
        (False, None, False, True, "outer_timeout"),
        (True, 0, False, False, "completed"),
    ],
)
def test_process_boundary_classification(started, code, observed, outer, want):
    from competition_tools.check_native_process_delivery import classify_process

    result = classify_process(
        started=started,
        exit_code=code,
        observation_expired=observed,
        outer_expired=outer,
    )
    assert result["status"] == want
    assert result["exit_code"] == code
    assert result["synthetic"] is True


@pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="Native PowerShell is not installed"
)
def test_native_success_has_timing_without_raw_streams(tmp_path):
    from competition_tools.check_native_process_delivery import (
        measure_synthetic_process,
    )

    value = measure_synthetic_process(tmp_path / "native", timeout_seconds=10)
    assert value["status"] == "completed"
    assert value["exit_code"] == 0
    assert value["wall_seconds"] >= 0
    assert value["started_at"] <= value["observed_at"]
    assert "synthetic-sentinel" not in json.dumps(value)
    assert str(tmp_path) not in json.dumps(value)


@pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="Native PowerShell is not installed"
)
@pytest.mark.parametrize(
    "mode,seconds,status,code",
    [
        ("exit7", 5, "child_failed", 7),
        ("sleep", 1, "observation_timeout", None),
        ("start-failure", 1, "start_failed", None),
        ("sleep", 20, "outer_timeout", None),
    ],
)
def test_native_failure_stages_are_distinct(tmp_path, mode, seconds, status, code):
    from competition_tools.check_native_process_delivery import (
        measure_synthetic_process,
    )

    value = measure_synthetic_process(
        tmp_path / "native", timeout_seconds=seconds, mode=mode
    )
    assert value["status"] == status
    assert value["exit_code"] == code
