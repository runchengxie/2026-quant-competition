"""Synthetic integration input construction cannot attest real data."""

import hashlib
import json

import pytest

from competition_tools.check_accounting_comparison import build_inputs
from test_accounting_comparison import legacy


def test_synthetic_inputs_bind_exact_bars_and_explicit_single_lag(tmp_path):
    bars = {
        "schema_version": "competition.synthetic_daily_bars.v1",
        "synthetic": True,
        "market": "US",
        "bars": [
            {"date": day, "code": "US.DEMO_A", "close": value}
            for day, value in [
                ("2026-01-31", "10"),
                ("2026-02-01", "11"),
                ("2026-02-02", "12"),
            ]
        ],
    }
    source = tmp_path / "bars.json"
    source.write_text(json.dumps(bars))
    retained = legacy()
    retained["input_fingerprint"] = hashlib.sha256(source.read_bytes()).hexdigest()
    build_inputs(tmp_path / "case", retained, source)
    asset = json.loads((tmp_path / "case/asset.json").read_text())
    request = json.loads((tmp_path / "case/request.json").read_text())
    assert asset["decisions"][0]["clock"]["decision_at"] == "2026-01-31T16:01:00Z"
    assert asset["decisions"][0]["execution_times"] == {
        "US.DEMO_A": "2026-02-01T09:00:00Z"
    }
    execution = next(
        p for p in asset["prices"] if p["price_at"] == "2026-02-01T09:00:00Z"
    )
    assert execution["price"] == "10"
    assert (
        request["input_fingerprint"]
        == hashlib.sha256((tmp_path / "case/asset.json").read_bytes()).hexdigest()
    )
    assert asset["synthetic"] is True
    assert asset["instruments"][0]["asset_type"] == "equity"
    with pytest.raises(FileExistsError):
        build_inputs(tmp_path / "case", retained, source)
    retained["synthetic"] = False
    with pytest.raises(ValueError, match="SYNTHETIC_ONLY"):
        build_inputs(tmp_path / "real", retained, source)
