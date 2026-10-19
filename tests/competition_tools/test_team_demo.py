"""Demo failures and destination boundaries must remain explicit."""

import json
import sys

import pytest

from competition_tools.team.config import TeamConfig
from competition_tools.team.demo import run_demo
from competition_tools.team.processes import interpreter


@pytest.mark.parametrize("project", ["equity", "crypto"])
def test_demo_refuses_existing_output(tmp_path, project):
    value = run_demo(project, TeamConfig(tmp_path, tmp_path / "env"), tmp_path)
    assert value["issue_codes"] == ["INVALID_OUTPUT"]
    assert value["synthetic"] is True


def test_demo_refuses_source_destination(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    value = run_demo("equity", TeamConfig(tmp_path, tmp_path / "env"), root / "output")
    assert value["issue_codes"] == ["INVALID_OUTPUT"]
    assert not (root / "output").exists()


def test_missing_environment_preserves_ownership_marker(tmp_path):
    output = tmp_path / "new"
    value = run_demo("crypto", TeamConfig(tmp_path, tmp_path / "env"), output)
    assert value["issue_codes"] == ["ENVIRONMENT_UNAVAILABLE"]
    assert not output.exists()


def test_failed_real_interpreter_does_not_succeed(tmp_path):
    config = TeamConfig(tmp_path, tmp_path / "env")
    python = interpreter(config, "equity-lab")
    python.parent.mkdir(parents=True)
    # Symlink the current interpreter: it lacks the leaf package after source injection is removed.
    try:
        python.symlink_to(sys.executable)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable on this host")
    output = tmp_path / "attempt"
    value = run_demo("equity", config, output)
    assert value["status"] == "blocked"
    assert value["issue_codes"] == ["CHILD_COMMAND_FAILED"]
    assert "Traceback" not in json.dumps(value)
    assert (output / "team-run.json").is_file()
    assert list((output / "logs").iterdir())
