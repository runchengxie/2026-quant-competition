"""A frozen retrospective plan binds bytes, dates and fixed assumptions."""

import csv
import json
from datetime import date, timedelta

import pytest
from competition_tools.datasets.storage import write_manifest
from competition_tools.evaluation.study_plan import freeze_study

COSTS = {"US": [20, 40], "HK": [30, 60], "crypto": [0, 10, 25]}


def crypto_manifest(root, *, days=600, partial=False):
    root.mkdir(parents=True)
    (root / ".dataset-owner").write_text("competition.dataset.v1")
    (root / "normalized").mkdir()
    dates = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(days)]
    for product in ["BTCUSDT", "ETHUSDT"]:
        with (root / "normalized" / f"{product}.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            writer.writerows([[day, 100, 100, 100, 100, 1] for day in dates])
    spec = {
        "schema": "competition.dataset_spec.v1",
        "source": "binance_spot",
        "dataset_id": "synthetic-study",
        "version": "v1",
        "market": "crypto",
        "quote_currency": "USDT",
        "products": ["BTCUSDT", "ETHUSDT"],
        "start": dates[0],
        "end": dates[-1],
        "calendar": "365",
        "timezone": "UTC",
        "price_basis": "raw",
        "universe_status": "fixed_current",
        "budget": {"requests": 20, "bytes": 1000000, "seconds": 60},
    }
    (root / "receipt.json").write_text(
        json.dumps(
            {"status": "partial" if partial else "acquired", "coverage": {}, "gaps": []}
        )
    )
    write_manifest(spec, root)
    return root / "manifest.json"


def identity(root):
    for directory in ["src", "research/equity-lab/src", "research/crypto-mm/src"]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    return {"commit": "a" * 40, "source_root": str(root), "source_sha256": "b" * 64}


def test_short_history_is_blocked_without_zero_returns(tmp_path):
    manifest = crypto_manifest(tmp_path / "data", days=300)
    plan = freeze_study(
        {
            "schema": "competition.evaluation_spec.v2",
            "manifests": [str(manifest)],
            "costs": COSTS,
        },
        tmp_path / "plan",
        code_identity=identity(tmp_path / "code"),
    )
    job = next(j for j in plan["jobs"] if j["market"] == "crypto")
    assert job["status"] == "blocked"
    assert job["reason"] == "INSUFFICIENT_HISTORY"
    assert "net_return" not in job


def test_frozen_folds_costs_and_missing_markets_are_explicit(tmp_path):
    manifest = crypto_manifest(tmp_path / "data")
    spec = {
        "schema": "competition.evaluation_spec.v2",
        "manifests": [str(manifest)],
        "costs": COSTS,
    }
    plan = freeze_study(
        spec, tmp_path / "plan", code_identity=identity(tmp_path / "code")
    )
    ready = [j for j in plan["jobs"] if j["status"] == "planned"]
    assert len(ready) == 27
    assert {j["strategy"] for j in ready} == {
        "equal_weight",
        "momentum_63d",
        "trend_200d",
    }
    assert {j["fee_bps"] for j in ready} == {0, 10, 25}
    assert min(j["fold"]["start"] for j in ready) == "2023-09-10"
    assert all(j["fold"]["scoring_periods"] == 90 for j in ready)
    assert all(j["accepted_research"] is False for j in ready)
    assert {j["market"] for j in plan["jobs"] if j["status"] == "blocked"} == {
        "US",
        "HK",
    }
    assert len({j["job_id"] for j in ready}) == len(ready)
    assert json.loads((tmp_path / "plan/plan.json").read_text()) == plan
    with pytest.raises(FileExistsError):
        freeze_study(spec, tmp_path / "plan", code_identity=identity(tmp_path / "code"))


def test_partial_parent_uses_hashed_slice_without_relabel_or_copy(tmp_path):
    manifest = crypto_manifest(tmp_path / "data", partial=True)
    before = manifest.read_bytes()
    plan = freeze_study(
        {
            "schema": "competition.evaluation_spec.v2",
            "manifests": [str(manifest)],
            "costs": COSTS,
        },
        tmp_path / "plan",
        code_identity=identity(tmp_path / "code"),
    )
    assert manifest.read_bytes() == before
    assert json.loads(before)["status"] == "partial"
    assert plan["inputs"][0]["slice"]["schema"] == "competition.study_input_slice.v1"
    assert plan["inputs"][0]["slice"]["parent_status"] == "partial"
    assert not list((tmp_path / "plan").rglob("*.csv"))


def test_unknown_cost_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="INVALID_STUDY_SPEC"):
        freeze_study(
            {
                "schema": "competition.evaluation_spec.v2",
                "manifests": [],
                "costs": COSTS | {"extra": [0]},
            },
            tmp_path / "plan",
            code_identity=identity(tmp_path / "code"),
        )
