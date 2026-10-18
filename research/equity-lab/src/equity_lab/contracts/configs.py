from __future__ import annotations

from typing import Any

KNOWN_MARKETS = {"HK", "US", "CN"}
NUMERIC_RISK_LIMITS = {
    "max_single_name_weight",
    "max_gross_exposure",
    "max_daily_turnover",
}


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_non_empty_string(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def validate_strategy_config(
    strategy_cfg: dict[str, Any],
    required_keys: list[str],
) -> dict[str, Any]:
    cfg = _require_mapping(strategy_cfg, "strategy config")
    missing = [key for key in required_keys if key not in cfg]
    if missing:
        raise ValueError(f"strategy config is missing required keys: {missing}")

    for key in ["name", "universe", "position_sizing"]:
        if key in cfg:
            _require_non_empty_string(cfg[key], f"strategy config {key}")

    if str(cfg.get("position_sizing", "equal_weight")).strip() != "equal_weight":
        raise ValueError(f"unsupported position_sizing: {cfg.get('position_sizing')}")

    if cfg.get("max_positions") is not None and int(cfg["max_positions"]) < 0:
        raise ValueError("max_positions cannot be negative")

    risk_limits = cfg.get("risk_limits", {}) or {}
    if not isinstance(risk_limits, dict):
        raise ValueError("strategy config risk_limits must be a mapping")
    for key in NUMERIC_RISK_LIMITS:
        if key in risk_limits and float(risk_limits[key]) < 0:
            raise ValueError(f"risk_limits.{key} cannot be negative")
    return cfg


def validate_sector_config(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _require_mapping(payload, "sector config")
    sectors = cfg.get("sectors")
    if not isinstance(sectors, list) or not sectors:
        raise ValueError("sector config sectors must be a non-empty list")

    seen_names: set[tuple[str, str, str]] = set()
    for idx, sector in enumerate(sectors):
        if not isinstance(sector, dict):
            raise ValueError(f"sectors[{idx}] must be a mapping")
        market = _require_non_empty_string(sector.get("market"), f"sectors[{idx}].market").upper()
        if market not in KNOWN_MARKETS:
            raise ValueError(f"sectors[{idx}].market is unsupported: {market}")
        category = _require_non_empty_string(
            sector.get("category", "general"),
            f"sectors[{idx}].category",
        )
        name = _require_non_empty_string(sector.get("name"), f"sectors[{idx}].name")
        key = (market, category, name)
        if key in seen_names:
            raise ValueError(f"duplicate sector definition: {key}")
        seen_names.add(key)

        members = sector.get("members")
        if not isinstance(members, list) or not members:
            raise ValueError(f"sectors[{idx}].members must be a non-empty list")
        for member_idx, member in enumerate(members):
            if not isinstance(member, dict):
                raise ValueError(f"sectors[{idx}].members[{member_idx}] must be a mapping")
            _require_non_empty_string(
                member.get("code"),
                f"sectors[{idx}].members[{member_idx}].code",
            )
    return cfg
