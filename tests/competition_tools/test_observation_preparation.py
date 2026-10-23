"""Preparation cannot turn already collected catch-up into prospective results."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from competition_tools.datasets.storage import write_manifest
from competition_tools.team.config import TeamConfig


def test_us_inventory_counts_qualifications_and_overlap():
    from competition_tools.evaluation.observation_preparation import us_refresh_inventory

    instruments = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "JNJ", "XOM", "PG", "SPY"]
    value = us_refresh_inventory(instruments, ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09"], "2025-01-10", retained_bytes=100)
    assert len(value["requests"]) == 22
    assert sum(r["kind"] == "history" for r in value["requests"]) == 11
    assert value["overlap_start"] == "2025-01-03"
    assert value["budget"]["bytes"] == 10485760
    assert value["activation_required"] is True
    with pytest.raises(ValueError):
        us_refresh_inventory(instruments, ["2025-01-02"], "2025-01-10", retained_bytes=10485761)


def test_preparation_help_needs_no_gateway_or_config(capsys):
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as exit:
        main(["observation-prepare", "--help"])
    assert exit.value.code == 0
    assert "us-refresh" in capsys.readouterr().out


def crypto_parent(tmp_path, *, gap=False):
    from competition_tools.datasets.binance_daily import PRODUCTS

    root = tmp_path / "data"
    (root / "normalized").mkdir(parents=True)
    (root / ".dataset-owner").write_text("competition.dataset.v1")
    end = date(2025, 1, 2)
    dates = [(end - timedelta(days=i)).isoformat() for i in reversed(range(252))]
    if gap:
        dates.pop(100)
    for p in PRODUCTS:
        (root / "normalized" / f"{p}.csv").write_text("date,open,high,low,close,volume\n" + "".join(f"{d},1,2,.5,1,10\n" for d in dates))
    spec = dict(schema="competition.dataset_spec.v1", dataset_id="fixture", version="v1", source="binance_spot", market="crypto", products=sorted(PRODUCTS), quote_currency="USDT", start=dates[0], end=dates[-1], timezone="UTC", calendar="365", price_basis="raw", universe_status="fixed_current", budget=dict(requests=20, bytes=10000, seconds=600))
    manifest = write_manifest(spec, root)
    manifest["observed_at"] = "2025-01-03T00:00:00+00:00"
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root / "manifest.json"


@pytest.mark.parametrize("state", ["fresh", "stale", "gap"])
def test_preparation_is_zero_observations_and_requires_fresh_common_warmup(tmp_path, state):
    from competition_tools.evaluation.observation_preparation import prepare_observation
    from competition_tools.evaluation.observation_registry import freeze_observation
    from test_observation_registry import fixture_protocol

    (tmp_path / "old").mkdir()
    protocol = fixture_protocol(tmp_path / "old")
    freeze_observation(protocol, tmp_path / "old-registry", now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    manifest = crypto_parent(tmp_path, gap=state == "gap")
    value = prepare_observation(TeamConfig(tmp_path, tmp_path / "env"), manifest, tmp_path / "prepared", parent_registry=tmp_path / "old-registry", now=datetime(2025, 1, 4 if state == "stale" else 3, tzinfo=timezone.utc))
    assert value["observations"] == 0
    assert value["status"] == ("ready_for_freeze_review" if state == "fresh" else "blocked")
    assert value["next_eligible_date"] == "2025-01-03"
    assert value["candidates"] == ["trend200_vol40_strict", "ew_trend_gross_matched", "ew_legacy"]
    assert value["new_protocol_id"] is None
    assert json.loads((tmp_path / "prepared/preparation.json").read_text()) == value
    assert not (tmp_path / "prepared/protocol.json").exists()


def test_per_market_freeze_keeps_six_candidates_and_external_relationship(tmp_path):
    from competition_tools.evaluation.observation_preparation import prepare_observation, freeze_prepared_market
    from competition_tools.evaluation.observation_registry import freeze_observation, TRUSTED_AVAILABILITY_EVIDENCE
    from test_observation_registry import fixture_protocol

    (tmp_path / "old").mkdir()
    protocol=fixture_protocol(tmp_path / "old")
    parent=tmp_path / "parent-registry"
    freeze_observation(protocol,parent,now=datetime(2025,1,1,tzinfo=timezone.utc))
    manifest=crypto_parent(tmp_path)
    config=TeamConfig(tmp_path,tmp_path / "env")
    now=datetime(2025,1,3,tzinfo=timezone.utc)
    prepare_observation(config,manifest,tmp_path / "prepared",parent_registry=parent,now=now)
    status=freeze_prepared_market(config,tmp_path / "prepared/preparation.json",parent,tmp_path / "new-registry",now=now,source_root=__import__('pathlib').Path(protocol["source_identity"]["source_root"]))
    assert status["observations"]==0
    frozen=json.loads((tmp_path / "new-registry/protocol.json").read_text())
    assert frozen["template"]["candidates"]==protocol["candidates"]
    assert frozen["template"]["known_cutoff"].startswith("2025-01-02")
    assert set(frozen["template"])==set(protocol)
    relationship=json.loads((tmp_path / "new-registry/relationship.json").read_text())
    assert relationship["new_protocol_id"]==status["protocol_id"]
    assert relationship["market"]=="crypto"
    assert not TRUSTED_AVAILABILITY_EVIDENCE
    with pytest.raises(ValueError,match="STALE"):
        freeze_prepared_market(config,tmp_path / "prepared/preparation.json",parent,tmp_path / "stale-registry",now=datetime(2025,1,4,tzinfo=timezone.utc),source_root=__import__('pathlib').Path(protocol["source_identity"]["source_root"]))
    assert not (tmp_path / "stale-registry").exists()
