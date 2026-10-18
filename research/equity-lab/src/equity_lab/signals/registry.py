# Discover locally installed signal modules.

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType

SUPPORT_MODULES = {"__init__.py", "registry.py"}


@dataclass(frozen=True)
class SignalSpec:
    name: str
    display_name: str
    description: str


def signal_dir() -> Path:
    return Path(__file__).resolve().parent       # Module directory


def discover_signal_names() -> list[str]:
    names: list[str] = []
    for path in sorted(signal_dir().glob("*.py")):
        if path.name.startswith("_") or path.name in SUPPORT_MODULES:
            continue
        names.append(path.stem)
    return names


def load_signal_module(name: str) -> ModuleType:
    normalized = str(name).strip()
    if not normalized:
        raise ValueError("signal name cannot be empty")
    if normalized not in discover_signal_names():
        raise ValueError(f"unknown signal: {normalized}")
    return import_module(f"equity_lab.signals.{normalized}")


def describe_signal(name: str) -> SignalSpec:
    module = load_signal_module(name)
    signal_name = str(getattr(module, "SIGNAL_NAME", name)).strip()
    display_name = str(getattr(module, "DISPLAY_NAME", signal_name)).strip()
    description = str(getattr(module, "DESCRIPTION", "")).strip()
    return SignalSpec(
        name=signal_name,
        display_name=display_name,
        description=description,
    )


def list_signal_specs() -> list[SignalSpec]:
    return [describe_signal(name) for name in discover_signal_names()]
