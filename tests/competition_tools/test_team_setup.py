"""Setup invokes real child processes with isolated argument vectors."""

import json
import os
from pathlib import Path
import sys

import pytest

from competition_tools.team.config import TeamConfig
from competition_tools.team.processes import child_environment, run_child
from competition_tools.team.setup import setup

ROOT = Path(__file__).resolve().parents[2]


def test_child_environment_is_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "secret-source")
    monkeypatch.setenv("PYTHONHOME", "secret-home")
    env = child_environment(TeamConfig(tmp_path, tmp_path / "envs"))
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert os.environ["PYTHONPATH"] == "secret-source"


def test_child_timeout():
    import subprocess

    with pytest.raises(subprocess.TimeoutExpired):
        run_child(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            environment=child_environment(TeamConfig(Path.cwd(), Path.cwd())),
            timeout=1,
        )


def test_offline_locked_projects_with_real_fake_uv(tmp_path, monkeypatch):
    # A Python launcher prefix is portable on Windows and POSIX and uses no shell.
    log = tmp_path / "record.jsonl"
    fake = tmp_path / "fake uv.py"
    fake.write_text(
        "import json,os,sys\nfrom pathlib import Path\n"
        'with open(os.environ["TEAM_TEST_LOG"],"a") as f: f.write(json.dumps({"argv":sys.argv[1:],"env":os.environ.get("UV_PROJECT_ENVIRONMENT"),"path":os.environ.get("PYTHONPATH")})+"\\n")\n'
        'p=Path(os.environ["UV_PROJECT_ENVIRONMENT"])/("Scripts/python.exe" if os.name=="nt" else "bin/python")\np.parent.mkdir(parents=True,exist_ok=True)\np.touch()\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TEAM_TEST_LOG", str(log))
    monkeypatch.setenv("PYTHONPATH", "do-not-forward")
    value = setup(
        TeamConfig(tmp_path / "data", tmp_path / "env spaces"),
        ROOT,
        "offline",
        uv_executable=[sys.executable, str(fake)],
    )
    assert value["status"] == "completed"
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 3
    assert len({row["env"] for row in records}) == 3
    assert all("--locked" in row["argv"] and row["path"] is None for row in records)
    assert all(
        "platform-compare" not in str(row) and "ibkr" not in str(row) for row in records
    )


def test_missing_uv_and_bad_repository_are_blocked(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    assert setup(config, ROOT, "offline", uv_executable="no-such-uv-command")[
        "issue_codes"
    ] == ["TOOL_UNAVAILABLE"]
    assert setup(config, tmp_path, "offline")["issue_codes"] == ["INVALID_REPOSITORY"]


def test_failed_child_output_is_not_public(tmp_path):
    fake = tmp_path / "fail.py"
    fake.write_text(
        'print("credential-sentinel");raise SystemExit(7)', encoding="utf-8"
    )
    value = setup(
        TeamConfig(tmp_path / "data", tmp_path / "env"),
        ROOT,
        "offline",
        uv_executable=[sys.executable, str(fake)],
    )
    assert value["issue_codes"] == ["CHILD_COMMAND_FAILED"]
    assert "credential-sentinel" not in json.dumps(value)
