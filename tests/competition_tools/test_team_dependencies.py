"""All competition profiles must remain independent of external quant frameworks."""

import ast
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def test_root_runtime_dependencies_remain_empty():
    assert (
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "dependencies"
        ]
        == []
    )


def test_team_imports_do_not_load_research_or_frameworks():
    forbidden = {
        "equity_lab",
        "crypto_mm",
        "portfolio_backtester",
        "research_contracts",
    }
    for path in (ROOT / "src/competition_tools/team").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Import):
                assert (
                    not {alias.name.split(".")[0] for alias in node.names} & forbidden
                )
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden


def test_framework_checks_are_separate_from_default_research():
    default = (ROOT / ".github/workflows/research.yml").read_text(encoding="utf-8")
    assert "accounting-provider" not in default
    optional = (ROOT / ".github/workflows/platform-comparison.yml").read_text(
        encoding="utf-8"
    )
    assert "research/platform-compare/**" in optional
    assert "check_accounting_comparison" in optional
    assert "workflow_dispatch:" in optional


def test_default_ci_exercises_team_delivery():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "check_team_delivery" in text
    assert "python -m competition_tools.team setup" in text


def test_core_lockfiles_exclude_framework_distributions():
    for relative in (
        ".",
        "research/equity-lab",
        "research/crypto-mm",
        "research/platform-compare",
    ):
        lock = tomllib.loads((ROOT / relative / "uv.lock").read_text(encoding="utf-8"))
        assert not any(
            package["name"].startswith(
                ("quant-", "research-contracts", "portfolio-backtester")
            )
            for package in lock["package"]
        )


def test_all_packages_exclude_framework_imports():
    forbidden = {"portfolio_backtester", "research_contracts", "quant_execution_engine"}
    for folder in (
        "src",
        "research/equity-lab/src",
        "research/crypto-mm/src",
        "research/platform-compare/src",
    ):
        for path in (ROOT / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[0] not in forbidden, path
                elif isinstance(node, ast.Import):
                    assert (
                        not {alias.name.split(".")[0] for alias in node.names}
                        & forbidden
                    ), path
