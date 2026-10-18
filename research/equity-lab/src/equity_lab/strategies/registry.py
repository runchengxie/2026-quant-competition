from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType

SUPPORT_MODULES = {"__init__.py", "registry.py", "common.py"}


@dataclass(frozen=True)
class StrategySpec:
    name: str
    display_name: str
    description: str
    default_config_name: str
    supported_markets: list[str]
    required_config_keys: list[str]
    default_signal_kwargs: dict[str, object]


def strategy_dir() -> Path:
    return Path(__file__).resolve().parent


def discover_strategy_names() -> list[str]:
    names: list[str] = []
    for path in sorted(strategy_dir().glob("*.py")):
        if path.name.startswith("_") or path.name in SUPPORT_MODULES:
            continue
        names.append(path.stem)
    return names


def load_strategy_module(name: str) -> ModuleType:
    normalized = str(name).strip()
    if not normalized:
        raise ValueError("strategy name cannot be empty")
    if normalized not in discover_strategy_names():
        raise ValueError(f"unknown strategy: {normalized}")
    return import_module(f"equity_lab.strategies.{normalized}")


def describe_strategy(name: str) -> StrategySpec:
    module = load_strategy_module(name)
    strategy_name = str(getattr(module, "STRATEGY_NAME", name)).strip()
    display_name = str(getattr(module, "DISPLAY_NAME", strategy_name)).strip()
    description = str(getattr(module, "DESCRIPTION", "")).strip()
    default_config_name = str(getattr(module, "DEFAULT_CONFIG_NAME", strategy_name)).strip()
    supported_markets = [
        str(value).upper().strip()
        for value in list(getattr(module, "SUPPORTED_MARKETS", []))
        if str(value).strip()
    ]
    required_config_keys = [
        str(value).strip()
        for value in list(getattr(module, "REQUIRED_CONFIG_KEYS", []))
        if str(value).strip()
    ]
    default_signal_kwargs = dict(getattr(module, "DEFAULT_SIGNAL_KWARGS", {}) or {})

    return StrategySpec(
        name=strategy_name,
        display_name=display_name,
        description=description,
        default_config_name=default_config_name,
        supported_markets=supported_markets,
        required_config_keys=required_config_keys,
        default_signal_kwargs=default_signal_kwargs,
    )


def list_strategy_specs() -> list[StrategySpec]:
    return [describe_strategy(name) for name in discover_strategy_names()]
