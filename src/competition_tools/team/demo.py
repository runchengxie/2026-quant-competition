"""Run existing leaf demos in a new owned external directory."""

import json
from pathlib import Path
import subprocess

from .config import TeamConfig
from .paths import validate_external
from .processes import child_environment, envelope, interpreter, run_child


def run_demo(project: str, config: TeamConfig, output_root: Path) -> dict:
    def result(issues=None):
        return envelope(
            "demo", issues=issues, projects=[{"name": project}], synthetic=True
        )

    if project not in {"equity", "crypto"}:
        return result(["INVALID_PROJECT"])
    try:
        output = validate_external(output_root)
        if output.exists():
            return result(["INVALID_OUTPUT"])
    except (OSError, ValueError):
        return result(["INVALID_OUTPUT"])
    python = interpreter(config, "equity-lab" if project == "equity" else "crypto-mm")
    if not python.is_file():
        return result(["ENVIRONMENT_UNAVAILABLE"])
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        return result(["INVALID_OUTPUT"])
    marker = output / "team-run.json"
    marker.write_text(
        json.dumps(
            {
                "schema_version": "competition.team_run.v1",
                "project": project,
                "synthetic": True,
                "status": "partial",
            }
        ),
        encoding="utf-8",
    )
    (output / "logs").mkdir()
    environment = child_environment(
        TeamConfig(output / "data", config.environment_root)
    )
    if project == "equity":
        root = str(output / "equity")
        commands = [
            ["-m", "equity_lab.cli", "demo", "--root", root],
            [
                "-m",
                "equity_lab.cli",
                "backtest",
                "--strategy",
                "equal_weight",
                "--root",
                root,
            ],
        ]
    else:
        commands = [
            ["-m", "crypto_mm.demo"],
            ["-m", "crypto_mm.commands.audit_data", "--json"],
            [
                "-m",
                "crypto_mm.commands.backtest_cli",
                "--strategy",
                "B0",
                "--days",
                "2026-03-19",
            ],
        ]
    try:
        for index, command in enumerate(commands):
            child = run_child(
                [str(python), *command], environment=environment, timeout=300
            )
            (output / "logs" / f"{index}.log").write_text(
                child.stdout + "\n" + child.stderr, encoding="utf-8"
            )
            if child.returncode:
                return result(["CHILD_COMMAND_FAILED"])
    except subprocess.TimeoutExpired:
        return result(["CHILD_TIMEOUT"])
    except OSError:
        return result(["CHILD_IO_FAILED"])
    marker.write_text(
        json.dumps(
            {
                "schema_version": "competition.team_run.v1",
                "project": project,
                "synthetic": True,
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )
    return result()
