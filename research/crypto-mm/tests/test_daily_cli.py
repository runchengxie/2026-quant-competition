import os
import subprocess
import sys


def test_daily_help_in_fresh_home_without_workspace_configuration(tmp_path):
    env = os.environ.copy()
    for key in (
        "DATA_ROOT",
        "CONFIG_ROOT",
        "WORKSPACE_CONFIG",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        env.pop(key, None)
    env["HOME"] = env["USERPROFILE"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "crypto_mm.daily", "--help"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert "--products" in result.stdout
    assert not list(tmp_path.iterdir())
