"""Demo failures and destination boundaries must remain explicit."""

import json
from pathlib import Path
import subprocess
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


@pytest.mark.parametrize("fail_at", ["initialize", "finalize"])
def test_marker_io_failures_are_blocked(tmp_path, monkeypatch, fail_at):
    import competition_tools.team.demo as demo

    config = TeamConfig(tmp_path, tmp_path / "env")
    python = interpreter(config, "equity-lab")
    python.parent.mkdir(parents=True)
    python.touch()
    original = Path.write_text
    attempts = 0

    def failing_write(path, *args, **kwargs):
        nonlocal attempts
        if path.name == "team-run.json":
            attempts += 1
            if attempts == (1 if fail_at == "initialize" else 2):
                raise OSError("private-path-and-credential-sentinel")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)
    monkeypatch.setattr(
        demo, "run_child", lambda *a, **k: subprocess.CompletedProcess([], 0, "", "")
    )
    value = run_demo("equity", config, tmp_path / "output")
    assert value["issue_codes"] == ["CHILD_IO_FAILED"]
    assert "sentinel" not in json.dumps(value)
    assert (tmp_path / "output").is_dir()


def test_invalid_demo_configuration_keeps_synthetic_boolean(tmp_path, capsys):
    from competition_tools.team.__main__ import main

    assert (
        main(
            [
                "demo",
                "equity",
                "--config",
                str(tmp_path / "missing.toml"),
                "--output-root",
                str(tmp_path / "output"),
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["synthetic"] is True
