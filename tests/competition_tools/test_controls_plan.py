"""Frozen controls preserve the complete comparison grid and consumed hashes."""

from datetime import date, timedelta
from pathlib import Path
import json

import pytest

from competition_tools.evaluation.controls import plan as planner
from competition_tools.evaluation.controls.contracts import validate_job
from competition_tools.evaluation.study_identity import source_identity
from test_controls_contracts import controls_spec


def inputs(spec, market):
    days = 953 if market == "US" else 1369
    dates = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(days)]
    return dict(
        market=market,
        quote_currency="USD" if market == "US" else "USDT",
        manifest=spec["manifests"][market],
        manifest_sha256=spec["expected_input_hashes"][market],
        products=["A", "B"],
        benchmark="SPY" if market == "US" else None,
        dates=dates,
        input_files=[],
        parent_status="acquired",
        slice={},
    )


def test_complete_cached_grid_is_420(tmp_path, monkeypatch):
    spec = controls_spec(tmp_path)
    monkeypatch.setattr(planner, "load_study_input", lambda p: inputs(spec, p.stem))
    # Source replay is tested independently; this test isolates folding/identity.
    monkeypatch.setattr(
        planner, "snapshot_source", lambda root, out: {"synthetic": True}
    )
    source = source_identity(Path(__file__).resolve().parents[2])
    plan = planner.freeze_controls(spec, tmp_path / "frozen", code_identity=source)
    assert len(plan["jobs"]) == 420
    assert sum(j["market"] == "US" for j in plan["jobs"]) == 132
    assert sum(j["market"] == "crypto" for j in plan["jobs"]) == 288
    assert len({j["job_id"] for j in plan["jobs"]}) == 420
    for job in plan["jobs"]:
        validate_job(job)
        assert len(job["dates"]) == 252 + job["fold"]["scoring_periods"]
        assert job["plan_sha256"] == plan["plan_sha256"]
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/strategy-controls-plan.v1.schema.json"
        ).read_text()
    )
    Draft202012Validator(schema).validate(plan)


def test_snapshot_keeps_exact_executed_bytes_and_rejects_dirty_source(tmp_path):
    from test_ablation_source import fixture_repo
    from competition_tools.evaluation.controls.source import snapshot_source
    from competition_tools.datasets.storage import digest

    root = fixture_repo(tmp_path / "checkout")
    receipt = snapshot_source(root, tmp_path / "snapshot")
    copied = Path(receipt["source_root"])
    for original in root.rglob("*.py"):
        assert digest(original) == digest(copied / original.relative_to(root))
    (root / "src/changed.py").write_text("VALUE = 1\n")
    with pytest.raises(ValueError, match="DIRTY_CONTROLS_SOURCE"):
        snapshot_source(root, tmp_path / "dirty-snapshot")


def test_changed_input_or_code_blocks_before_child(tmp_path, monkeypatch):
    spec = controls_spec(tmp_path)
    monkeypatch.setattr(planner, "load_study_input", lambda p: inputs(spec, p.stem))
    monkeypatch.setattr(
        planner, "snapshot_source", lambda root, out: {"synthetic": True}
    )
    source = source_identity(Path(__file__).resolve().parents[2])
    Path(spec["manifests"]["US"]).write_text('{"changed":true}')
    with pytest.raises(ValueError, match="CONTROLS_INPUT_CHANGED"):
        planner.freeze_controls(spec, tmp_path / "bad-input", code_identity=source)
    spec = controls_spec(tmp_path)
    source["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="CONTROLS_SOURCE_CHANGED"):
        planner.freeze_controls(spec, tmp_path / "bad-source", code_identity=source)
