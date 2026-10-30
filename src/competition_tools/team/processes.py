"""Bounded child processes without shell or inherited source injection."""

import os
from pathlib import Path
import signal
import subprocess

from .config import TeamConfig


def child_environment(config: TeamConfig) -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment["DATA_ROOT"] = str(config.data_root)
    environment["GLOBAL_MARKET_RESEARCH_DATA_ROOT"] = str(config.storage_root)
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONUTF8"] = "1"
    return environment


def interpreter(config: TeamConfig, project: str) -> Path:
    return (
        config.environment_root
        / project
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )


def run_child(
    argv: list[str], *, environment: dict[str, str], timeout: int
) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        argv,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        # Kill the tree while its parent still exists, then drain the pipes.
        if os.name == "nt":
            killer = (
                Path(os.environ.get("SystemRoot", "C:/Windows"))
                / "System32/taskkill.exe"
            )
            try:
                subprocess.run(
                    [str(killer), "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            finally:
                if process.poll() is None:
                    process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.communicate(timeout=15)
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def envelope(
    action: str,
    *,
    issues: list[str] | None = None,
    projects: list | None = None,
    synthetic: bool | None = None,
) -> dict:
    return {
        "schema_version": "competition.team_result.v1",
        "action": action,
        "status": "blocked" if issues else "completed",
        "issue_codes": issues or [],
        "projects": projects or [],
        "synthetic": synthetic,
    }
