"""Bounded child processes without shell or inherited source injection."""

import os
from pathlib import Path
import subprocess

from .config import TeamConfig


def child_environment(config: TeamConfig) -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment["DATA_ROOT"] = str(config.data_root)
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
    return subprocess.run(
        argv,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )


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
