"""Dataset contracts protect external immutable data and honest coverage."""

import json

import pytest

from competition_tools.datasets.spec import load_spec
from competition_tools.datasets.storage import publish_dataset, verify_manifest
from competition_tools.datasets.quality import validate_bars


def specification():
    return {
        "schema": "competition.dataset_spec.v1",
        "dataset_id": "spot-study",
        "version": "v1",
        "source": "binance_spot",
        "market": "crypto",
        "products": ["BTCUSDT", "ETHUSDT"],
        "quote_currency": "USDT",
        "start": "2024-10-01",
        "end": "2024-12-31",
        "timezone": "UTC",
        "calendar": "365",
        "price_basis": "raw",
        "universe_status": "fixed_current",
        "budget": {"requests": 20, "bytes": 26214400, "seconds": 600},
    }


def test_spec_rejects_unknown_source_and_invalid_range(tmp_path):
    path = tmp_path / "spec.json"
    value = specification()
    for change in (
        {"source": "silent-fallback"},
        {"end": "2020-01-01"},
        {"dataset_id": "../escape"},
        {"products": ["BTCUSD"]},
        {"budget": {"requests": True, "bytes": 100, "seconds": 10}},
    ):
        path.write_text(json.dumps(value | change))
        with pytest.raises(ValueError):
            load_spec(path)
    path.write_text(json.dumps(value))
    assert load_spec(path)["universe_status"] == "fixed_current"


def test_publish_is_exclusive_and_detects_corruption(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / ".dataset-owner").write_text("competition.dataset.v1")
    (staging / "normalized").mkdir()
    (staging / "normalized/bars.csv").write_text("date,close\n2024-10-01,1\n")
    destination = tmp_path / "published"
    publish_dataset(specification(), staging, destination)
    manifest = destination / "manifest.json"
    assert verify_manifest(manifest)["schema"] == "competition.dataset_manifest.v1"
    with pytest.raises((ValueError, FileExistsError)):
        publish_dataset(specification(), staging, destination)
    (destination / "normalized/bars.csv").write_text("corrupt")
    with pytest.raises(ValueError, match="HASH"):
        verify_manifest(manifest)


@pytest.mark.parametrize(
    "row",
    [
        ["2024-01-01", "1", "2", "0", "nan", "1"],
        ["2024-01-01", "1", "0", "2", "1", "1"],
        ["2024-01-01", "1", "2", "0", "1", "-1"],
    ],
)
def test_invalid_bars_rejected(row):
    with pytest.raises(ValueError):
        validate_bars([row])


def test_duplicate_dates_rejected():
    row = ["2024-01-01", "1", "2", "0.5", "1", "1"]
    with pytest.raises(ValueError):
        validate_bars([row, row])


def test_broker_trades_cannot_be_mislabeled_raw(tmp_path):
    path = tmp_path / "spec.json"
    value = specification() | {
        "source": "ibkr",
        "market": "US",
        "quote_currency": "USD",
        "products": ["SPY"],
        "timezone": "America/New_York",
        "calendar": "XNYS",
    }
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="BROKER_BASIS"):
        load_spec(path)
    path.write_text(json.dumps(value | {"price_basis": "split_adjusted"}))
    assert load_spec(path)["price_basis"] == "split_adjusted"
