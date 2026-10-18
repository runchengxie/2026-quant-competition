"""Signal generation logic."""

from .registry import (
    SignalSpec,
    describe_signal,
    discover_signal_names,
    list_signal_specs,
    load_signal_module,
)

__all__ = [
    "SignalSpec",
    "describe_signal",
    "discover_signal_names",
    "list_signal_specs",
    "load_signal_module",
]
