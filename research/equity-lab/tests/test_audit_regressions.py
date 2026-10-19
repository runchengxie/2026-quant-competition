import json

import pandas as pd
import pytest
import yaml

from equity_lab.backtest.prep import prepare_market_panel
from equity_lab.demo import build_demo_data
from equity_lab.services.backtest import run_backtest_service


def test_comparison_artifacts_exist_and_match_declared_summary(tmp_path):
    build_demo_data(tmp_path)
    result = run_backtest_service(
        "sma_cross",
        root=tmp_path,
        compare_benchmarks=True,
        benchmark_list="equal_weight",
    )
    summary_path = (
        result.artifact_bundle["summary_path"].parent
        / "benchmark_equal_weight/summary.json"
    )
    summary = json.loads(summary_path.read_text())
    for key in ("portfolio_daily", "positions_daily"):
        path = summary_path.parent / summary["artifacts"][key]
        assert path.is_file(), f"Missing declared artifact: {path.name}"
        assert not pd.read_csv(path).empty


def test_missing_bar_flags_describe_original_data_before_fill():
    frame = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "code": "HK.DEMO_A",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 10.0,
            },
            {
                "date": "2026-01-05",
                "code": "HK.DEMO_A",
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.0,
                "volume": 10.0,
            },
        ]
    )
    result = prepare_market_panel(
        frame, trading_dates=pd.bdate_range("2026-01-01", periods=3)
    )
    missing = result.iloc[1]
    assert missing["close"] == 100.0
    assert bool(missing["is_missing_bar"])
    assert bool(missing["is_interpolated"])
    assert bool(missing["is_zero_volume"])
    assert bool(missing["is_halt"])
    assert not bool(result.iloc[0]["is_interpolated"])


def test_explicit_market_cost_profile_applies_without_benchmark(tmp_path):
    build_demo_data(tmp_path)
    config = tmp_path / "backtest.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "benchmark": None,
                "market": "HK",
                "commission_bps": 0,
                "slippage_bps": 0,
                "regulation_bps": 0,
                "market_cost_profiles": {
                    "CN": {"commission_bps": 1},
                    "HK": {"commission_bps": 25},
                },
            }
        )
    )
    result = run_backtest_service("equal_weight", root=tmp_path, config_path=config)
    positions = result.positions
    active = positions[positions["turnover"] > 0]
    assert not active.empty
    assert (active["cost"] / active["turnover"]).tolist() == pytest.approx(
        [0.0025] * len(active)
    )
