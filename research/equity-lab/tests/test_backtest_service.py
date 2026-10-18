from __future__ import annotations

from pathlib import Path

import pandas as pd

from equity_lab.cli import run_backtest
from equity_lab.data.market_data import MarketDataPaths, save_bars
from equity_lab.services.backtest import run_backtest_service


def _write_market_data(root: Path, codes: list[str]) -> Path:
    market_root = root / "artifacts" / "data" / "processed" / "market"
    paths = MarketDataPaths(market_root)
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    for idx, code in enumerate(codes):
        rows = []
        for day, date in enumerate(dates):
            close = 100.0 + day * (1.0 + idx * 0.2)
            rows.append(
                {
                    "date": date,
                    "open": close - 0.5,
                    "high": close + 0.5,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1000 + day,
                    "code": code,
                }
            )
        save_bars(pd.DataFrame(rows), paths.symbol_file(code))
    return market_root


def _write_backtest_files(root: Path) -> tuple[Path, Path, Path]:
    codes = ["HK.00700", "HK.00941"]
    market_root = _write_market_data(root, codes)

    universe_path = root / "config" / "universe" / "hk_core_watchlist.txt"
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    universe_path.write_text("\n".join(codes) + "\n", encoding="utf-8")

    strategy_path = root / "config" / "strategies" / "sim_portfolio.yaml"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text(
        "\n".join(
            [
                "name: sim_portfolio",
                "universe: hk_core_watchlist",
                "max_positions: 2",
                "position_sizing: equal_weight",
                "signal:",
                "  short_window: 2",
                "  long_window: 5",
                "risk_limits:",
                "  max_single_name_weight: 0.6",
                "  max_gross_exposure: 1.0",
                "  max_daily_turnover: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config_path = root / "config" / "backtest" / "default.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "name: test-backtest",
                "initial_capital: 100000",
                "slippage_bps: 0",
                "commission_bps: 0",
                "regulation_bps: 0",
                f"price_path: {market_root}",
                f"report_path: {root / 'artifacts' / 'reports' / 'backtests'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path, strategy_path, universe_path


def test_backtest_service_runs_end_to_end_in_temp_project(tmp_path: Path) -> None:
    config_path, strategy_path, _universe_path = _write_backtest_files(tmp_path)

    result = run_backtest_service(
        "sma_cross",
        root=tmp_path,
        config_path=config_path,
        strategy_config_path=strategy_path,
    )

    assert result.strategy_name == "sma_cross"
    assert result.portfolio_path.exists()
    assert result.positions_path.exists()
    assert result.artifact_bundle["summary_path"].exists()
    assert result.latest_equity > 0
    assert result.artifact_bundle["summary"]["strategy_config"] == "config/strategies/sim_portfolio.yaml"


def test_backtest_command_uses_service_and_prints_outputs(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, strategy_path, universe_path = _write_backtest_files(tmp_path)
    monkeypatch.setenv("EQUITY_LAB_BACKTEST_CONFIG", str(config_path))
    monkeypatch.setenv("EQUITY_LAB_STRATEGY_CONFIG", str(strategy_path))
    monkeypatch.setenv("EQUITY_LAB_UNIVERSE_FILE", str(universe_path))

    run_backtest("sma_cross")

    captured = capsys.readouterr()
    assert "Backtest finished." in captured.out
    assert "Summary report:" in captured.out


def test_backtest_service_compare_benchmarks_runs_equal_weight(
    tmp_path: Path,
) -> None:
    config_path, strategy_path, _universe_path = _write_backtest_files(tmp_path)
    strategy_dir = tmp_path / "config" / "strategies"
    (strategy_dir / "equal_weight.yaml").write_text(
        "\n".join(
            [
                "name: equal_weight",
                "universe: hk_core_watchlist",
                "max_positions: null",
                "position_sizing: equal_weight",
                "signal: {}",
                "risk_limits:",
                "  max_single_name_weight: 0.6",
                "  max_gross_exposure: 1.0",
                "  max_daily_turnover: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (strategy_dir / "momentum_20d.yaml").write_text(
        "\n".join(
            [
                "name: momentum_20d",
                "universe: hk_core_watchlist",
                "max_positions: 2",
                "position_sizing: equal_weight",
                "signal:",
                "  lookback_days: 5",
                "  min_momentum: 0.0",
                "risk_limits:",
                "  max_single_name_weight: 0.6",
                "  max_gross_exposure: 1.0",
                "  max_daily_turnover: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_backtest_service(
        "sma_cross",
        root=tmp_path,
        config_path=config_path,
        strategy_config_path=strategy_path,
        compare_benchmarks=True,
        benchmark_list="equal_weight,momentum_20d",
    )

    assert [run["strategy"] for run in result.comparison_runs] == [
        "equal_weight",
        "momentum_20d",
    ]
    assert all(run.get("status") != "failed" for run in result.comparison_runs)
    assert result.artifact_bundle["summary"]["comparison"]["benchmark_count"] == 2
