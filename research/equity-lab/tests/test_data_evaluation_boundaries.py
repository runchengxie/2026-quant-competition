"""Data and evaluation remain usable without loading replay or plotting."""

import importlib
import os
import subprocess
import sys

import pandas as pd
import pytest

from equity_lab.data.preparation import prepare_market_panel
from equity_lab.evaluation.performance import compute_backtest_metrics
from equity_lab.evaluation.signals import (
    compute_hit_rate,
    compute_ic_metrics,
    slice_metric_signal,
)


def market_row(day, code, close):
    return dict(
        date=day, code=code, open=close, high=close, low=close, close=close, volume=10.0
    )


def test_preparation_retains_gap_flags_and_does_not_backfill_listing():
    source = pd.DataFrame(
        [
            market_row("2024-01-01", "A", 100.0),
            market_row("2024-01-03", "A", 102.0),
            market_row("2024-01-02", "B", 50.0),
        ]
    )
    before = source.copy(deep=True)
    actual = prepare_market_panel(
        source, trading_dates=pd.date_range("2024-01-01", periods=3)
    )
    gap = actual[
        (actual.code == "A") & (actual.date == pd.Timestamp("2024-01-02"))
    ].iloc[0]
    assert gap[["open", "high", "low", "close"]].tolist() == [100.0] * 4
    assert gap.volume == 0.0
    assert gap.is_missing_bar and gap.is_interpolated and gap.is_halt
    assert actual[actual.code == "B"].date.min() == pd.Timestamp("2024-01-02")
    pd.testing.assert_frame_equal(source, before)


def test_preparation_rejects_missing_columns_and_keeps_invalid_calendar_fallback():
    with pytest.raises(ValueError, match="market panel is missing columns"):
        prepare_market_panel(pd.DataFrame({"date": ["2024-01-01"]}))
    source = pd.DataFrame([market_row("2024-01-01", "A", 100.0)])
    pd.testing.assert_frame_equal(
        prepare_market_panel(source, trading_dates=["invalid"]),
        prepare_market_panel(source),
    )


def test_daily_signal_correlations_keep_score_and_label_priority():
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 3,
            "weight_score": [3, 2, 1],
            "signal": [1, 2, 3],
            "future_return": [0.03, 0.02, 0.01],
            "target_label": [0, 1, 1],
        }
    )
    assert compute_ic_metrics(frame) == pytest.approx((1.0, 1.0))


@pytest.mark.parametrize("scores, labels", [([1, 1, 1], [1, 2, 3]), ([1, 2], [1, 2])])
def test_undefined_signal_correlations_stay_unavailable(scores, labels):
    frame = pd.DataFrame(
        {"date": ["2024-01-01"] * len(scores), "signal": scores, "target_label": labels}
    )
    assert compute_ic_metrics(frame) == (None, None)


def test_legacy_pooled_fallback_is_preserved_for_sparse_daily_groups():
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "signal": [1, 2, 3],
            "future_return": [0.1, 0.2, 0.3],
        }
    )
    assert compute_ic_metrics(frame) == pytest.approx((1.0, 1.0))


def test_signal_status_filter_and_hit_rate_preserve_selected_denominator():
    frame = pd.DataFrame(
        {
            "signal": [1, 0, 1],
            "target_label": [1, 0, 0],
            "cnn_model_status": ["cnn_predicted", "cnn_predicted", "trained"],
        }
    )
    selected = slice_metric_signal(frame, "cnn_predicted")
    assert compute_hit_rate(selected) == 1.0
    assert compute_hit_rate(frame) == 0.5
    assert slice_metric_signal(
        frame.drop(columns="cnn_model_status"), "cnn_predicted"
    ).empty
    assert compute_hit_rate(pd.DataFrame()) is None


def test_performance_preserves_empty_and_benchmark_outputs():
    empty = compute_backtest_metrics(pd.DataFrame(), initial_capital=100.0)
    assert empty["final_equity"] == 100.0
    assert empty["trading_days"] == 0
    assert empty["sharpe_ratio"] is None
    assert empty["rank_ic"] is None
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "equity": [100.0, 110.0, 104.5],
            "daily_return": [0.0, 0.1, -0.05],
        }
    )
    benchmark = pd.Series([0.0, 0.02, 0.0], index=pd.to_datetime(frame.date))
    metrics = compute_backtest_metrics(
        frame, initial_capital=100.0, benchmark_returns=benchmark
    )
    assert metrics["total_return"] == pytest.approx(0.045)
    assert metrics["max_drawdown"] == pytest.approx(-0.05)
    assert metrics["benchmark_return"] == pytest.approx(0.02)
    assert metrics["benchmark_excess_return"] == pytest.approx(0.025)
    assert metrics["ic"] is None


@pytest.mark.parametrize("index", [[0, 1, 2], [10, 30, 90]])
def test_equity_only_portfolio_preserves_regime_return_alignment(index):
    dates = pd.date_range("2024-01-01", periods=3)
    portfolio = pd.DataFrame(
        {"date": dates, "equity": [100.0, 110.0, 104.5]}, index=index
    )
    signal = pd.DataFrame({"date": dates, "volatility_regime": ["low", "low", "high"]})
    actual = compute_backtest_metrics(
        portfolio, initial_capital=100.0, signal_df=signal
    )
    assert actual["volatility_regime_returns"] == pytest.approx(
        {"low": 0.1, "high": -0.05}
    )


def test_legacy_imports_reexport_the_same_canonical_functions():
    old_prep = importlib.import_module("equity_lab.backtest.prep")
    new_prep = importlib.import_module("equity_lab.data.preparation")
    old_metrics = importlib.import_module("equity_lab.backtest.metrics")
    new_metrics = importlib.import_module("equity_lab.evaluation.performance")
    assert old_prep.prepare_market_panel is new_prep.prepare_market_panel
    assert old_prep.REQUIRED_MARKET_COLUMNS is new_prep.REQUIRED_MARKET_COLUMNS
    for name in (
        "compute_backtest_metrics",
        "compute_daily_returns",
        "compute_drawdown_series",
        "compute_sharpe_ratio",
    ):
        assert getattr(old_metrics, name) is getattr(new_metrics, name)


def test_new_workflow_modules_import_without_replay_or_plotting(tmp_path):
    code = """
import sys
from equity_lab.data.preparation import prepare_market_panel
from equity_lab.evaluation.performance import compute_backtest_metrics
from equity_lab.evaluation.signals import compute_ic_metrics
for prefix in ('equity_lab.backtest', 'equity_lab.services', 'equity_lab.strategies', 'matplotlib', 'ib_insync'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        not in {"DATA_ROOT", "CONFIG_ROOT", "WORKSPACE_CONFIG", "XDG_CONFIG_HOME"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
