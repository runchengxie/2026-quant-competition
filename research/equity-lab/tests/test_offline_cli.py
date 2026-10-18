import json
import subprocess
import sys

import pytest

from equity_lab.demo import build_demo_data
from equity_lab.services.backtest import run_backtest_service
from equity_lab.signals import discover_signal_names
from equity_lab.strategies import discover_strategy_names, load_strategy_module


def test_demo_and_packaged_config_run_without_broker(tmp_path):
    paths = build_demo_data(tmp_path)
    assert len(paths) == 2
    assert json.loads((tmp_path / "demo-manifest.json").read_text())["synthetic"] is True
    result = run_backtest_service("equal_weight", root=tmp_path)
    assert result.portfolio_path.is_relative_to(tmp_path)
    assert result.artifact_bundle["summary"]["run_status"] == "completed"
    assert not any(name == "futu" or name.startswith("futu.") for name in sys.modules)
    with pytest.raises(FileExistsError):
        build_demo_data(tmp_path)


def test_exact_offline_strategies_and_cli_list():
    names = ["cnn_image_pattern", "cnn_pattern", "cnn_pattern_mvp", "cnn_walk_forward_rank",
             "equal_weight", "momentum_20d", "random_turnover", "sma_cross"]
    assert discover_strategy_names() == names
    assert discover_signal_names() == ["cnn_image_pattern", "cnn_pattern", "cnn_walk_forward_rank", "momentum", "sma"]
    process = subprocess.run([sys.executable, "-m", "equity_lab.cli", "list"],
                             capture_output=True, text=True, check=True)
    assert process.stdout.splitlines() == names


def test_failed_signal_is_visible_in_persisted_summary(tmp_path, monkeypatch):
    build_demo_data(tmp_path)
    module = load_strategy_module("equal_weight")

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic model failure")

    monkeypatch.setattr(module, "build_signal_frame", fail)
    result = run_backtest_service("equal_weight", root=tmp_path)
    summary = json.loads(result.artifact_bundle["summary_path"].read_text())
    assert summary["run_status"] == "strategy_fallback"
    assert "synthetic model failure" in summary["fallback_reasons"][0]


def test_comparison_does_not_hide_failed_baseline(tmp_path, monkeypatch):
    build_demo_data(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic baseline failure")

    monkeypatch.setattr(load_strategy_module("equal_weight"), "build_signal_frame", fail)
    result = run_backtest_service("sma_cross", root=tmp_path, compare_benchmarks=True,
                                  benchmark_list="equal_weight")
    assert result.comparison_runs[0]["status"] == "strategy_fallback"
    assert "synthetic baseline failure" in result.comparison_runs[0]["fallback_reasons"][0]
