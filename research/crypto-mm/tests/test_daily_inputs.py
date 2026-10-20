import hashlib
import json

import pytest

from crypto_mm.daily.inputs import load_daily


def fixture_manifest(tmp_path, body):
    path = tmp_path / "normalized/BTCUSDT.csv"
    path.parent.mkdir()
    path.write_text(body)
    manifest = {
        "schema": "competition.dataset_manifest.v1",
        "spec": {
            "source": "binance_spot",
            "market": "crypto",
            "calendar": "365",
            "timezone": "UTC",
            "quote_currency": "USDT",
            "price_basis": "raw",
            "products": ["BTCUSDT"],
            "universe_status": "fixed_current",
        },
        "files": [
            {
                "path": "normalized/BTCUSDT.csv",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        ],
    }
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(manifest))
    return target


def test_leaf_rejects_nonfinite_ohlcv_even_with_matching_hash(tmp_path):
    path = fixture_manifest(
        tmp_path, "date,open,high,low,close,volume\n2024-01-01,1,nan,0.5,1,10\n"
    )
    with pytest.raises(ValueError):
        load_daily(path)


def test_leaf_detects_mutated_dataset(tmp_path):
    path = fixture_manifest(
        tmp_path, "date,open,high,low,close,volume\n2024-01-01,1,2,0.5,1,10\n"
    )
    (tmp_path / "normalized/BTCUSDT.csv").write_text("changed")
    with pytest.raises(ValueError, match="HASH"):
        load_daily(path)


def test_explicit_subset_preserves_parent_manifest_identity(tmp_path):
    path = fixture_manifest(
        tmp_path, "date,open,high,low,close,volume\n2024-01-01,1,2,0.5,1,10\n"
    )
    result = load_daily(path, products=["BTCUSDT"])
    assert set(result["close"]) == {"BTCUSDT"}
    assert result["manifest_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="SUBSET"):
        load_daily(path, products=["UNKNOWNUSDT"])
