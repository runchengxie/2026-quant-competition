"""Exercise CLI contracts against small real Parquet inputs."""

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

import polars as pl
import pytest


@pytest.fixture
def cli_environment(tmp_path):
    shared = tmp_path / "data"
    raw = shared / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"
    for day in ("2026-03-19", "2026-03-20", "2026-03-21"):
        times = [datetime.fromisoformat(day) + timedelta(seconds=s) for s in (0, 1, 2, 120)]
        book = {"datetime": pl.Series(times, dtype=pl.Datetime("ns"))}
        for level in range(1, 21):
            book[f"bid_price_{level}"] = [100 - level * 0.1] * 4
            book[f"ask_price_{level}"] = [100 + level * 0.1] * 4
            book[f"bid_qty_{level}"] = [1.0] * 4
            book[f"ask_qty_{level}"] = [1.0] * 4
        frames = {
            "orderbook": pl.DataFrame(book),
            "trades": pl.DataFrame({
                "datetime": pl.Series(times, dtype=pl.Datetime("ns")),
                "price": [100.0] * 4, "size": [0.1] * 4,
                "is_maker_ask": [0, 1, 0, 1],
            }),
            "fundings": pl.DataFrame({
                "datetime": pl.Series(times, dtype=pl.Datetime("ns")),
                "funding_rate": [0.0] * 4,
            }),
        }
        for dataset, frame in frames.items():
            folder = raw / dataset
            folder.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(folder / f"{day}.parquet")
    env = {**os.environ, "DATA_ROOT": str(shared)}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return env


def run_cli(module, arguments, env, cwd):
    return subprocess.run(
        [sys.executable, "-m", module, *arguments], env=env, cwd=cwd,
        text=True, capture_output=True, timeout=30,
    )


@pytest.mark.parametrize("module", [
    "crypto_mm.commands.backtest_cli", "crypto_mm.commands.audit_data", "crypto_mm.research.analyze_signals",
])
def test_help_does_not_require_data_files(module, tmp_path, cli_environment):
    cli_environment["DATA_ROOT"] = str(tmp_path / "no-data")
    result = run_cli(module, ["--help"], cli_environment, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize("arguments", [
    ["--strategy", "unknown"], ["--days", "2026-03-22"],
    ["--inventory-skew-sensitivity", "--volatility-multiplier-sensitivity"],
])
def test_invalid_backtest_arguments_fail_before_reading_data(arguments, tmp_path, cli_environment):
    cli_environment["DATA_ROOT"] = str(tmp_path / "no-data")
    result = run_cli("crypto_mm.commands.backtest_cli", arguments, cli_environment, tmp_path)
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_backtest_defaults_and_selected_days(tmp_path, cli_environment):
    result = run_cli("crypto_mm.commands.backtest_cli", ["--days", "2026-03-19"], cli_environment, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "B0 mid-price baseline" in result.stdout
    assert "Period: 2026-03-19\n" in result.stdout
    assert "Funding cashflow: 0" in result.stdout
    assert not result.stdout.lstrip().startswith("{")


@pytest.mark.parametrize("days", [
    ["2026-03-20", "2026-03-19"], ["2026-03-19", "2026-03-19"],
])
def test_backtest_requires_strictly_increasing_days(days, tmp_path, cli_environment):
    result = run_cli("crypto_mm.commands.backtest_cli", ["--days", *days], cli_environment, tmp_path)
    assert result.returncode != 0
    assert "days must be strictly increasing" in result.stderr


@pytest.mark.parametrize("flag,heading", [
    ("--inventory-skew-sensitivity", "B0 inventory-skew sensitivity"),
    ("--volatility-multiplier-sensitivity", "B2 volatility-multiplier sensitivity"),
])
def test_sensitivity_dispatch_has_ten_cases(flag, heading, tmp_path, cli_environment):
    result = run_cli("crypto_mm.commands.backtest_cli", [flag, "--strategy", "B3", "--days", "2026-03-19"], cli_environment, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == heading
    assert len(result.stdout.splitlines()) == 12


def test_audit_json_and_summary_cover_all_datasets(tmp_path, cli_environment):
    result = run_cli("crypto_mm.commands.audit_data", ["--json"], cli_environment, tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["audit_version"] == 1
    assert report["reader"] == "polars"
    assert set(report["datasets"]) == {"orderbook", "trades", "fundings"}
    for daily in report["datasets"].values():
        assert len(daily) == 3
        assert sum(item["rows"] for item in daily) == 12
        assert all(not any(item["quality"].values()) for item in daily)
    assert [item["code"] for item in report["findings"]] == [
        "TIMEZONE_UNSPECIFIED", "FUNDING_IS_ROLLING",
    ]
    summary = run_cli("crypto_mm.commands.audit_data", [], cli_environment, tmp_path)
    assert summary.returncode == 0, summary.stderr
    assert "orderbook: rows=12, quality_failures=0" in summary.stdout
    assert "[WARNING] TIMEZONE_UNSPECIFIED" in summary.stdout


def test_signal_cli_runs_for_one_selected_day(tmp_path, cli_environment):
    result = run_cli("crypto_mm.research.analyze_signals", ["--days", "2026-03-19"], cli_environment, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "2026-03-19" in result.stdout
    assert "B1" in result.stdout and "B2" in result.stdout


def test_audit_rejects_missing_daily_file(tmp_path, cli_environment):
    raw = Path(cli_environment["DATA_ROOT"]) / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"
    (raw / "trades" / "2026-03-19.parquet").unlink()
    result = run_cli("crypto_mm.commands.audit_data", ["--json"], cli_environment, tmp_path)
    assert result.returncode != 0
    assert "trades: unexpected daily files" in result.stderr


def test_plot_api_writes_named_pngs_to_explicit_output(tmp_path, monkeypatch):
    from datetime import timezone
    from crypto_mm.backtest import build_backtest_engine
    from crypto_mm.commands import plot_results
    from crypto_mm.config import BacktestConfig

    engine, tracker = build_backtest_engine("B0", BacktestConfig())
    engine.account.mark_to_market(100.0)
    data = plot_results.StrategyPlotData(
        timestamps=(datetime(2026, 3, 19, tzinfo=timezone.utc),),
        equity=(0.0,), inventory=(0.0,), metrics=tracker.metrics(engine.account),
    )
    # Replace only the costly full-sample producer; exercise all real plot writers.
    monkeypatch.setattr(plot_results, "_run_strategies", lambda: {k: data for k in plot_results.STRATEGY_IDS})
    paths = plot_results.generate_figures(output_directory=tmp_path)
    assert [p.name for p in paths] == [
        "cumulative-pnl.png", "inventory-path.png", "strategy-comparison.png",
    ]
    assert all(p.parent == tmp_path and p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for p in paths)
