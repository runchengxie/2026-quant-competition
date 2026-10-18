from __future__ import annotations

from pathlib import Path

from equity_lab.contracts.configs import validate_strategy_config
from equity_lab.strategies import describe_strategy
from equity_lab.utils.config import _simple_yaml_load, load_yaml

ROOT = Path(__file__).resolve().parents[1]


def test_validate_strategy_config_accepts_current_yaml() -> None:
    spec = describe_strategy("sma_cross")
    cfg = load_yaml(
        ROOT / "src" / "equity_lab" / "config" / "strategies" / f"{spec.default_config_name}.yaml"
    )
    validate_strategy_config(cfg, spec.required_config_keys)


def test_validate_cnn_walk_forward_rank_config_accepts_current_yaml() -> None:
    spec = describe_strategy("cnn_walk_forward_rank")
    cfg = load_yaml(ROOT / "src" / "equity_lab" / "config" / "strategies" / f"{spec.default_config_name}.yaml")
    validate_strategy_config(cfg, spec.required_config_keys)




def test_validate_cnn_image_pattern_config_accepts_current_yaml() -> None:
    spec = describe_strategy("cnn_image_pattern")
    cfg = load_yaml(ROOT / "src" / "equity_lab" / "config" / "strategies" / f"{spec.default_config_name}.yaml")
    validate_strategy_config(cfg, spec.required_config_keys)




def test_validate_cnn_image_pattern_paper_ohlc_config_accepts_current_yaml() -> None:
    spec = describe_strategy("cnn_image_pattern")
    cfg = load_yaml(ROOT / "src" / "equity_lab" / "config" / "strategies" / "cnn_image_pattern_paper_ohlc.yaml")
    validate_strategy_config(cfg, spec.required_config_keys)


def test_validate_equal_weight_config_accepts_null_max_positions() -> None:
    spec = describe_strategy("equal_weight")
    cfg = load_yaml(ROOT / "src" / "equity_lab" / "config" / "strategies" / f"{spec.default_config_name}.yaml")

    validate_strategy_config(cfg, spec.required_config_keys)


def test_validate_strategy_config_rejects_negative_max_positions() -> None:
    try:
        validate_strategy_config(
            {
                "name": "x",
                "universe": "hk_core_watchlist",
                "position_sizing": "equal_weight",
                "max_positions": -1,
            },
            ["name", "universe", "position_sizing"],
        )
    except ValueError as exc:
        assert "max_positions" in str(exc)
    else:
        raise AssertionError("expected ValueError for negative max_positions")


def test_validate_strategy_config_rejects_missing_required_key() -> None:
    try:
        validate_strategy_config({"name": "x"}, ["name", "universe"])
    except ValueError as exc:
        assert "universe" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing required config keys")


def test_simple_yaml_parser_strips_inline_comments_from_scalars() -> None:
    cfg = _simple_yaml_load("fee_bps: 0.206  # fractional\nmax_positions: 8 # comment\n")
    assert cfg["fee_bps"] == 0.206
    assert cfg["max_positions"] == 8






