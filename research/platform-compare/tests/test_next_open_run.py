import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from platform_compare.accounting.backtest_bundle import BacktestEvidenceTier
from platform_compare.accounting.backtest_bundle_io import read_backtest_bundle
from platform_compare.next_open.loader import ASSET_FILES, FX_FILES
from platform_compare.next_open.run import run_experiment


def _run_fixture(tmp_path: Path, *, omit_session: tuple[str, str] | None = None):
    data_root = tmp_path / "inputs"
    data_root.mkdir()
    files = {}
    sessions = ("2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12")
    for instrument, filename in ASSET_FILES.items():
        rows = []
        for session in sessions:
            if omit_session == (instrument, session):
                continue
            rows.append(
                f"{session},10,11,9,10.5,100,10,1,first_regular_hours_trade_open,,false"
            )
        path = data_root / filename
        path.write_text(
            "date,open,high,low,close,volume,average,bar_count,price_semantics,available_at,execution_eligible\n"
            + "\n".join(rows)
            + "\n",
            encoding="utf-8",
        )
        files[filename] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    for filename in FX_FILES.values():
        rows = [
            f"{session},1.2,1.3,1.1,1.25,0,1.22,0,MIDPOINT_DAILY,,false"
            for session in sessions
        ]
        path = data_root / filename
        path.write_text(
            "date,open,high,low,close,volume,average,bar_count,price_semantics,available_at,execution_eligible\n"
            + "\n".join(rows)
            + "\n",
            encoding="utf-8",
        )
        files[filename] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (data_root / "dataset-manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "synthetic-global-etf",
                "analysis_cutoff_local_date": "2026-10-01",
                "execution_eligible": False,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    schedule_path = tmp_path / "target-schedule-v1.json"
    schedule_path.write_text(
        json.dumps(
            {
                "schema_version": "research.target_schedule.v1",
                "strategy_id": "synthetic-defended-rotation",
                "rebalances": [
                    {
                        "signal_as_of_date": "2026-03-10",
                        "targets": [
                            {"instrument_id": "US_SPY", "weight": "0.5"},
                            {"instrument_id": "HK_2800", "weight": "0.25"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "experiment.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "experiment_id": "synthetic-global-etf-next-open-v1",
                "strategy_id": "synthetic-defended-rotation",
                "data_root": str(data_root),
                "target_schedule_path": str(schedule_path),
                "signal_cutoff": "2026-10-01",
                "initial_cash_usd": "100000",
                "sizing_mode": "fractional",
                "max_price_age_days": 7,
                "max_fx_age_days": 7,
                "production_eligible": False,
                "return_basis": "usd_price_nav",
                "reference_cost_bps": {
                    "commission": 5,
                    "equity_slippage": 5,
                    "fx": 0,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return config_path


def test_run_writes_36_cost_scenarios_and_input_lock(tmp_path, monkeypatch):
    config_path = _run_fixture(tmp_path)
    output = tmp_path / "diagnostics"
    result = run_experiment(config_path, output)
    assert result["scenario_count"] == 36
    assert result["status"] == "completed"
    assert len(list((output / "scenarios").iterdir())) == 36
    lock = json.loads((output / "input-lock.json").read_text(encoding="utf-8"))
    assert lock["accounting_engine"]["engine"] == "competition.usd_price_ledger"
    assert lock["calendar"]["package"] == "exchange_calendars"
    assert lock["calendar"]["version"] == "4.13.2"
    assert lock["target_schedule_sha256"]
    assert len(lock["source_file_sha256"]) == 10


def test_run_outputs_diagnostic_only_without_order_fill_claim(tmp_path, monkeypatch):
    config_path = _run_fixture(tmp_path)
    output = tmp_path / "diagnostics"
    run_experiment(config_path, output)
    scenario_dir = next((output / "scenarios").iterdir())
    manifest = read_backtest_bundle(scenario_dir)
    assert manifest.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC
    assert pd.read_parquet(scenario_dir / "orders.parquet").empty
    assert pd.read_parquet(scenario_dir / "fills.parquet").empty
    note = (output / "result-note.md").read_text(encoding="utf-8")
    assert "research diagnostic" in note.lower()
    assert "not executable" in note.lower()


def test_run_refuses_output_inside_repository(tmp_path, monkeypatch):
    config_path = _run_fixture(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    with pytest.raises(ValueError, match="OUTPUT_IN_SOURCE"):
        run_experiment(config_path, repo_root / "runs" / "leak")


def test_run_reconciles_nav_and_transaction_costs(tmp_path, monkeypatch):
    config_path = _run_fixture(tmp_path)
    output = tmp_path / "diagnostics"
    run_experiment(config_path, output)
    rows = pd.read_csv(output / "cost-sensitivity.csv")
    assert len(rows) == 36
    nav_difference = (
        rows["ending_nav_usd"] - rows["ending_cash_usd"] - rows["ending_positions_usd"]
    ).abs()
    assert nav_difference.max() < 1e-8
    assert (rows["cumulative_costs_usd"] >= 0).all()
    assert set(rows["orders_submitted"]) == {False}
    assert set(rows["execution_eligible"]) == {False}


def test_run_records_missing_next_open_as_rejected_without_close_fallback(
    tmp_path, monkeypatch
):
    config_path = _run_fixture(tmp_path, omit_session=("HK_2800", "2026-03-11"))
    output = tmp_path / "rejected"
    result = run_experiment(config_path, output)
    assert result["status"] == "rejected_input"
    assert result["scenario_count"] == 0
    rejected = json.loads((output / "rejected-events.json").read_text(encoding="utf-8"))
    assert "missing source session bar" in rejected[0]["reason"]
    assert not (output / "scenarios").exists()
