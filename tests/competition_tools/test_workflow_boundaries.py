"""Architecture rules check real import edges, not naming alone."""

from pathlib import Path

import pytest

from competition_tools.check_workflow_boundaries import check_boundaries


def source(tmp_path, path, text):
    for name in ("src", "research/equity-lab/src", "research/crypto-mm/src"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "path, text",
    [
        ("src/apps/runner.py", "from crypto_mm.daily import controls\n"),
        (
            "research/equity-lab/src/equity_lab/data/x.py",
            "from ..backtest.engine import BacktestConfig\n",
        ),
        (
            "research/equity-lab/src/equity_lab/evaluation/x.py",
            "from equity_lab import backtest\n",
        ),
        (
            "research/crypto-mm/src/crypto_mm/portfolio/x.py",
            "from ..daily.study_accounting import account_periods\n",
        ),
        (
            "research/crypto-mm/src/crypto_mm/signals/x.py",
            "from ..portfolio.daily import build_control_targets\n",
        ),
        (
            "research/crypto-mm/src/crypto_mm/data/x.py",
            "import importlib as loader\nloader.import_module('crypto_mm.daily.controls')\n",
        ),
        (
            "research/crypto-mm/src/crypto_mm/portfolio/x.py",
            "from importlib import import_module as load\nload('..daily.controls', 'crypto_mm.portfolio')\n",
        ),
        (
            "research/equity-lab/src/equity_lab/data/x.py",
            "__import__('equity_lab.backtest')\n",
        ),
    ],
)
def test_forbidden_static_relative_and_constant_dynamic_edges_fail(
    tmp_path, path, text
):
    result = check_boundaries(source(tmp_path, path, text))
    assert result["status"] == "failed"
    assert result["violations"][0]["path"] == path
    assert result["violations"][0]["line"] > 0


def test_allowed_imports_and_similar_names_do_not_match_forbidden_prefixes(tmp_path):
    root = source(
        tmp_path,
        "research/crypto-mm/src/crypto_mm/portfolio/x.py",
        "from ..signals.daily_trend import hysteresis_states\nimport crypto_mm.daily_notes\n",
    )
    result = check_boundaries(root)
    assert result["status"] == "completed"
    assert result["files_checked"] == 1


def test_nonliteral_dynamic_import_in_pure_layer_is_not_claimed_checked(tmp_path):
    root = source(
        tmp_path,
        "research/equity-lab/src/equity_lab/data/x.py",
        "import importlib\nimportlib.import_module(name)\n",
    )
    assert check_boundaries(root)["violations"][0]["rule"] == "dynamic-unresolved"


@pytest.mark.parametrize(
    "prefix, allowed",
    [
        ("equity_lab.signals.", True),
        ("equity_lab.backtest.", False),
        ("equity_lab.", False),
    ],
)
def test_dynamic_registry_prefix_must_prove_it_cannot_reach_forbidden_layer(
    tmp_path, prefix, allowed
):
    code = (
        "from importlib import import_module\nimport_module(f'" + prefix + "{name}')\n"
    )
    root = source(
        tmp_path, "research/equity-lab/src/equity_lab/signals/registry.py", code
    )
    assert (check_boundaries(root)["status"] == "completed") is allowed


def test_pure_leaf_cannot_import_the_other_independent_package(tmp_path):
    root = source(
        tmp_path,
        "research/crypto-mm/src/crypto_mm/portfolio/x.py",
        "import equity_lab.portfolio\n",
    )
    assert check_boundaries(root)["status"] == "failed"


def test_missing_tree_and_invalid_python_fail(tmp_path):
    assert check_boundaries(tmp_path)["status"] == "failed"
    root = source(tmp_path, "src/example.py", "def broken(\n")
    assert check_boundaries(root)["violations"][0]["rule"] == "syntax"


def test_current_production_tree_respects_workflow_boundaries():
    result = check_boundaries(Path(__file__).resolve().parents[2])
    assert result["status"] == "completed", result["violations"]
    assert result["files_checked"] > 200
