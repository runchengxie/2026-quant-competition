"""The cross-environment CI check is an explicit, data-free entry point."""

import json
from pathlib import Path
import subprocess
import sys


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
