"""Experiments must work when every external framework import is unavailable."""

import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_owner_contract import fixture
from test_next_open_run import _run_fixture


BLOCK_FRAMEWORK = """
import importlib.abc
import sys
class BlockFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'portfolio_backtester', 'research_contracts', 'quant_platform'}:
            raise ImportError('External framework import blocked: ' + fullname)
sys.meta_path.insert(0, BlockFramework())
"""


def test_distribution_does_not_install_frameworks():
    requirements = importlib.metadata.requires("competition-platform-compare") or []
    assert not any(
        name in requirement.lower()
        for requirement in requirements
        for name in ("quant-platform", "research-contracts")
    )


def test_framework_distributions_are_absent():
    for name in ("quant-platform", "research-contracts"):
        with pytest.raises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.distribution(name)


def test_installed_accounting_includes_license_and_exact_source_inventory():
    import hashlib
    import platform_compare.accounting

    root = Path(platform_compare.accounting.__file__).parent
    assert "Apache License" in (root / "LICENSE-APACHE-2.0.txt").read_text()
    assert "quant-platform" in (root / "NOTICE.txt").read_text()
    inventory = json.loads((root / "ORIGIN.json").read_text())
    assert inventory["commit"] == "28a32ba707ad72d1eb68cde5075663e1b3819ac7"
    for item in inventory["files"]:
        prefix = "src/platform_compare/accounting/"
        if item["destination"].startswith(prefix):
            path = root / item["destination"][len(prefix) :]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item["local_sha256"]


def test_accounting_runs_and_verifies_without_framework_imports(tmp_path):
    request, _, _ = fixture(tmp_path)
    code = (
        BLOCK_FRAMEWORK
        + """
import json
from pathlib import Path
from platform_compare.owner_adapter import run_request, verify_result
request, root, output = map(Path, sys.argv[1:])
result = run_request(request, root, output)
assert verify_result(request, root, output) == result
assert result['final_nav_usd'] == '150'
assert result['provider']['repository'] == '2026-quant-competition'
assert result['orders_submitted'] is False
print(json.dumps(result))
"""
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(request),
            str(tmp_path),
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["final_cash_usd"] == "50"


def test_next_open_runs_without_framework_imports(tmp_path):
    config = _run_fixture(tmp_path)
    code = (
        BLOCK_FRAMEWORK
        + """
import json
from pathlib import Path
from platform_compare.next_open.run import run_experiment
result = run_experiment(Path(sys.argv[1]), Path(sys.argv[2]))
assert result['status'] == 'completed'
print(json.dumps(result))
"""
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(config), str(tmp_path / "output")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lock = json.loads((tmp_path / "output" / "input-lock.json").read_text())
    assert lock["accounting_engine"]["repository"] == "2026-quant-competition"
    assert "platform_revision" not in lock
