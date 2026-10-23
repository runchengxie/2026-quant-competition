"""Exercise the installed module entry point rather than mocking dispatch."""

import json
import subprocess
import sys

from test_daily_controls_inputs import create_control


def test_actual_controls_batch_cli_and_help(tmp_path):
    _, job = create_control(tmp_path / "input")
    path = tmp_path / "batch.json"
    path.write_text(
        json.dumps(
            dict(
                schema="competition.strategy_controls_batch.v1",
                plan_sha256=job["plan_sha256"],
                market="crypto",
                jobs=[job],
            )
        )
    )
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.daily.controls_cli",
            "--jobs",
            str(path),
            "--output-root",
            str(tmp_path / "output"),
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert child.returncode == 0, child.stderr + child.stdout
    assert json.loads(child.stdout)["status"] == "completed"
    assert (tmp_path / "output" / job["job_id"] / "result.json").is_file()
    help_result = subprocess.run(
        [sys.executable, "-m", "crypto_mm.daily.controls_cli", "--help"],
        capture_output=True,
        timeout=15,
    )
    assert help_result.returncode == 0
