"""The cross-environment CI check is an explicit, data-free entry point."""

import json
from pathlib import Path
import subprocess
import sys
import pytest


def test_integration_help_without_research_packages():
    result = subprocess.run(
        [sys.executable, "-m", "competition_tools.check_research_receipts", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--leaf-python" in result.stdout


def test_pages_links_localized_acceptance_guide_and_preserves_snapshot():
    root = Path(__file__).resolve().parents[2]
    source = (root / "site/src/components/ValidationResults.astro").read_text(
        encoding="utf-8"
    )
    assert "research-acceptance" in source
    for locale, suffix in (("en", ""), ("zh-CN", ".zh-CN")):
        catalog = json.loads(
            (root / f"site/src/i18n/{locale}.json").read_text(encoding="utf-8")
        )
        assert catalog["validation"]["acceptanceGuide"]
        assert (root / f"docs/research/research-acceptance{suffix}.md").is_file()
    snapshot = json.loads(
        (root / "site/src/data/strategy-validation.json").read_text(encoding="utf-8")
    )
    assert len(snapshot["results"]) == 24


@pytest.mark.parametrize(
    "module,arguments",
    [
        (
            "research_acceptance",
            [
                "--receipt",
                "dummy.json",
                "--dataset-root",
                ".",
                "D:/private/account-123/data.csv",
            ],
        ),
        (
            "experiment_acceptance",
            [
                "--plan",
                "dummy.json",
                "--input-receipt",
                "dummy.json",
                "--summary",
                "dummy.json",
                "--observations",
                "dummy.json",
                "--dataset-root",
                ".",
                "--output",
                "dummy.json",
                "D:/private/account-123/data.csv",
            ],
        ),
        (
            "check_research_receipts",
            [
                "--project",
                "D:/private/account-123/data.csv",
                "--leaf-python",
                "dummy",
                "--output-root",
                "dummy",
            ],
        ),
    ],
)
def test_root_parser_errors_do_not_echo_private_arguments(module, arguments):
    result = subprocess.run(
        [sys.executable, "-m", "competition_tools." + module] + arguments,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "D:/private" not in result.stdout + result.stderr
    assert "INVALID_ARGUMENTS" in result.stdout + result.stderr
