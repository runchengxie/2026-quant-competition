import json

import pytest

from packages.audit.artifacts import publish_frozen_run


TARGETS = {
    "schema_version": "1.0",
    "strategy_id": "hk-pit-ml-index-enhancement",
    "market": "HK",
    "as_of": "2026-09-03T00:00:00Z",
    "targets": [{"symbol": "0700.HK", "weight": "1.0", "quantity": "100"}],
}
LINEAGE = {"strategy_id": TARGETS["strategy_id"], "market": "HK", "research_run_id": "research-001"}
CONFIG = {"execution": {"environment": "paper", "dry_run": True}}


def test_publish_frozen_run_writes_complete_artifact(tmp_path):
    run = publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                             config=CONFIG, metrics={"sharpe": 0.8})
    assert run.joinpath("targets.json").is_file()
    evidence = json.loads(run.joinpath("evidence.json").read_text(encoding="utf-8"))
    assert evidence["environment"] == "paper"
    assert evidence["strategy_id"] == TARGETS["strategy_id"]


def test_publish_frozen_run_does_not_overwrite_existing_run(tmp_path):
    publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                       config=CONFIG, metrics={})
    with pytest.raises(FileExistsError):
        publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                           config=CONFIG, metrics={})
