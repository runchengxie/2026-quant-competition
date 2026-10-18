from __future__ import annotations

from equity_lab.strategies import (
    describe_strategy,
    discover_strategy_names,
    list_strategy_specs,
    load_strategy_module,
)


def test_discover_strategy_names_smoke() -> None:
    names = discover_strategy_names()
    assert "common" not in names
    assert "sma_cross" in names
    assert "momentum_20d" in names
    assert "cnn_pattern" in names
    assert "cnn_pattern_mvp" in names
    assert "cnn_image_pattern" in names
    assert "cnn_walk_forward_rank" in names


def test_load_strategy_module_smoke() -> None:
    module = load_strategy_module("sma_cross")
    assert module.STRATEGY_NAME == "sma_cross"
    assert hasattr(module, "build_signal_frame")


def test_describe_strategy_smoke() -> None:
    spec = describe_strategy("sma_cross")
    assert spec.name == "sma_cross"
    assert spec.default_config_name == "sim_portfolio"
    assert "HK" in spec.supported_markets
    assert "universe" in spec.required_config_keys
    assert spec.default_signal_kwargs["short_window"] == 20


def test_list_strategy_specs_smoke() -> None:
    specs = list_strategy_specs()
    assert any(spec.name == "sma_cross" for spec in specs)
    assert any(spec.name == "momentum_20d" for spec in specs)
    assert any(spec.name == "cnn_pattern" for spec in specs)
    assert any(spec.name == "cnn_pattern_mvp" for spec in specs)
    assert any(spec.name == "cnn_image_pattern" for spec in specs)
    assert any(spec.name == "cnn_walk_forward_rank" for spec in specs)
