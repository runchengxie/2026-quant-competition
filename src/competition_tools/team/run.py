"""Dispatch explicit international experiments without importing their code."""

import json
from pathlib import Path
import subprocess
import uuid

from .config import TeamConfig
from .paths import validate_external
from .processes import child_environment, envelope, interpreter, run_child

EXPERIMENTS = {
    "international": ("equity-lab", "equity_lab.international.six_market_run"),
    "next-open": ("platform-compare", "platform_compare.next_open.run"),
}


def run_experiment(
    project: str, config: TeamConfig, experiment_config: Path, output_root: Path
) -> dict:
    def result(issues=None):
        return envelope("run", issues=issues, projects=[{"name": project}])

    if project not in EXPERIMENTS:
        return result(["INVALID_PROJECT"])
    try:
        output = validate_external(output_root)
        if output.exists():
            return result(["INVALID_OUTPUT"])
    except (OSError, ValueError):
        return result(["INVALID_OUTPUT"])
    name, module = EXPERIMENTS[project]
    python = interpreter(config, name)
    if not python.is_file():
        return result(["ENVIRONMENT_UNAVAILABLE"])
    try:
        log_root = validate_external(
            config.data_root / "2026-quant-competition/team-runs"
        )
        log_root.mkdir(parents=True, exist_ok=True)
        log = log_root / f"{uuid.uuid4().hex}.log"
        child = run_child(
            [
                str(python),
                "-m",
                module,
                "--config",
                str(experiment_config.resolve()),
                "--output-dir",
                str(output),
                "--json",
            ],
            environment=child_environment(config),
            timeout=1800,
        )
        with log.open("x", encoding="utf-8") as stream:
            stream.write(child.stdout + "\n" + child.stderr)
        if child.returncode:
            return result(["CHILD_COMMAND_FAILED"])
        value = json.loads(child.stdout)
        if not isinstance(value, dict) or value.get("status") in {
            "blocked",
            "rejected_input",
        }:
            return result(["INVALID_CHILD_RESULT"])
    except subprocess.TimeoutExpired:
        return result(["CHILD_TIMEOUT"])
    except (OSError, ValueError):
        return result(["CHILD_IO_FAILED"])
    return result()
