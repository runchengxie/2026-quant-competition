import importlib
import subprocess
import sys
import tempfile
from pathlib import Path


MODULES = (
    "packages.contracts",
    "adapters.ibkr",
    "apps.execution_runner",
    "strategies.global_etf_rotation",
    "competition_tools",
)


def test_python_packages_import_from_an_unrelated_working_directory():
    module = importlib.import_module("competition_tools.check_pages_content")
    repository_root = Path(module.__file__).resolve().parents[2]
    assert module.SITE == repository_root / "site"
    assert module.SITE.is_dir()

    code = "import importlib; " + "; ".join(
        f"importlib.import_module({name!r})" for name in MODULES
    )
    temp_root = Path(__file__).resolve().parents[1] / ".pytest-tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as working_directory:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=working_directory,
            capture_output=True,
            text=True,
            check=False,
        )

    assert completed.returncode == 0, completed.stderr
