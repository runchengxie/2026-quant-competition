"""The combined installed contract stays offline and is wired into CI."""

from pathlib import Path


def test_combined_delivery_has_bound_synthetic_execution_inputs(tmp_path):
    from competition_tools.check_strategy_evidence_delivery import execution_fixture
    from competition_tools.datasets.storage import digest

    path, spec = execution_fixture(tmp_path)
    assert path.is_file()
    assert spec["synthetic"] is True
    assert spec["files"]["AAPL"]["sha256"] == digest(tmp_path / "AAPL.csv")
    assert spec["schedule"][0]["decision_at"] == "2025-03-07T21:02:00Z"


def test_combined_delivery_is_exercised_by_ci():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/platform-comparison.yml").read_text()
    assert "competition_tools.check_strategy_evidence_delivery" in workflow
    assert "--profile framework" in workflow
