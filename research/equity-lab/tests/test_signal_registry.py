from __future__ import annotations

from equity_lab.signals import (
    describe_signal,
    discover_signal_names,
    list_signal_specs,
    load_signal_module,
)


def test_discover_signal_names_smoke() -> None:
    names = discover_signal_names()
    assert "sma" in names
    assert "momentum" in names
    assert "cnn_pattern" in names
    assert "cnn_image_pattern" in names
    assert "cnn_walk_forward_rank" in names


def test_describe_signal_smoke() -> None:
    spec = describe_signal("sma")
    assert spec.name == "sma"
    assert "Moving Average" in spec.display_name


def test_load_signal_module_smoke() -> None:
    module = load_signal_module("sma")
    assert module.SIGNAL_NAME == "sma"
    assert hasattr(module, "generate_sma_signal")


def test_list_signal_specs_smoke() -> None:
    specs = list_signal_specs()
    assert any(spec.name == "sma" for spec in specs)
    assert any(spec.name == "momentum" for spec in specs)
    assert any(spec.name == "cnn_pattern" for spec in specs)
    assert any(spec.name == "cnn_image_pattern" for spec in specs)
    assert any(spec.name == "cnn_walk_forward_rank" for spec in specs)
