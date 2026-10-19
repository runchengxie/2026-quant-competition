import hashlib
import json
from datetime import date

import pytest

from platform_compare.next_open.loader import load_inputs

ASSETS = {
    "US_SPY": "US_SPY.csv",
    "HK_2800": "HK_2800.csv",
    "UK_ISF": "UK_ISF.csv",
    "AU_STW": "AU_STW.csv",
    "SG_ES3": "SG_ES3.csv",
}
FX_FILES = {
    "AUDUSD": "FX_AUDUSD.csv",
    "GBPUSD": "FX_GBPUSD.csv",
    "USDCAD": "FX_USDCAD.csv",
    "USDHKD": "FX_USDHKD.csv",
    "USDSGD": "FX_USDSGD.csv",
}


def _write_inputs(tmp_path, *, asset_names=None, asset_rows=None):
    asset_names = ASSETS if asset_names is None else asset_names
    data_root = tmp_path / "bars"
    data_root.mkdir()
    files = {}
    for name, filename in asset_names.items():
        row = (asset_rows or {}).get(
            name,
            "2026-10-01,10,11,9,10.5,100,10,1,first_regular_hours_trade_open,,false",
        )
        path = data_root / filename
        path.write_text(
            "date,open,high,low,close,volume,average,bar_count,price_semantics,available_at,execution_eligible\n"
            + row
            + "\n",
            encoding="utf-8",
        )
        files[filename] = {
            "rows": 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    for filename in FX_FILES.values():
        path = data_root / filename
        path.write_text(
            "date,open,high,low,close,volume,average,bar_count,price_semantics,available_at,execution_eligible\n"
            "2026-10-01,1.2,1.3,1.1,1.25,0,1.22,0,MIDPOINT_DAILY,,false\n",
            encoding="utf-8",
        )
        files[filename] = {
            "rows": 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (data_root / "dataset-manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "synthetic",
                "analysis_cutoff_local_date": "2026-10-01",
                "execution_eligible": False,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    schedule = tmp_path / "target-schedule-v1.json"
    schedule.write_text(
        json.dumps(
            {
                "schema_version": "research.target_schedule.v1",
                "strategy_id": "synthetic",
                "rebalances": [{"signal_as_of_date": "2026-10-01", "targets": []}],
            }
        ),
        encoding="utf-8",
    )
    return data_root, schedule


def test_load_inputs_locks_manifest_and_hashes(tmp_path):
    data_root, schedule = _write_inputs(tmp_path)
    result = load_inputs(data_root, schedule, cutoff_date=date(2026, 10, 1))
    assert set(result.assets) == set(ASSETS)
    assert set(result.fx) == set(FX_FILES)
    assert result.dataset_manifest["dataset_id"] == "synthetic"
    assert (
        result.input_hashes["target-schedule-v1.json"]
        == hashlib.sha256(schedule.read_bytes()).hexdigest()
    )
    assert all(len(value) == 64 for value in result.input_hashes.values())


@pytest.mark.parametrize(
    ("row", "error"),
    [
        (
            "2026-10-02,10,11,9,10.5,100,10,1,first_regular_hours_trade_open,,false",
            "after the signal cutoff",
        ),
        (
            "2026-10-01,10,9,9,10.5,100,10,1,first_regular_hours_trade_open,,false",
            "inconsistent high/low",
        ),
        (
            "2026-10-01,10,11,9,10.5,100,10,1,first_regular_hours_trade_open,,true",
            "execution eligibility",
        ),
        (
            "2026-10-01,0,11,9,10.5,100,10,1,first_regular_hours_trade_open,,false",
            "non-positive",
        ),
    ],
)
def test_load_inputs_rejects_cutoff_and_invalid_ohlc_rows(tmp_path, row, error):
    data_root, schedule = _write_inputs(tmp_path, asset_rows={"US_SPY": row})
    with pytest.raises(ValueError, match=error):
        load_inputs(data_root, schedule, cutoff_date=date(2026, 10, 1))


def test_load_inputs_rejects_duplicate_asset_sessions(tmp_path):
    data_root, schedule = _write_inputs(tmp_path)
    path = data_root / ASSETS["US_SPY"]
    with path.open(encoding="utf-8") as stream:
        duplicate_row = stream.readlines()[1]
    with path.open("a", encoding="utf-8") as stream:
        stream.write(duplicate_row)
    manifest_path = data_root / "dataset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][ASSETS["US_SPY"]]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate dates"):
        load_inputs(data_root, schedule, cutoff_date=date(2026, 10, 1))


def test_load_inputs_requires_five_etfs_and_five_fx_pairs(tmp_path):
    missing_xiu = dict(ASSETS)
    missing_xiu.pop("SG_ES3")
    missing_xiu["CA_XIU"] = "CA_XIU.csv"
    data_root, schedule = _write_inputs(tmp_path, asset_names=missing_xiu)
    with pytest.raises(ValueError, match="asset universe"):
        load_inputs(data_root, schedule, cutoff_date=date(2026, 10, 1))
