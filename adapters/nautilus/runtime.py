"""NautilusTrader dependency discovery without an import-time hard dependency."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True, slots=True)
class NautilusRuntimeStatus:
    """Whether the optional NautilusTrader runtime is installed locally."""

    available: bool
    message: str


def describe_nautilus_runtime() -> NautilusRuntimeStatus:
    """Describe the optional runtime without importing its native extensions."""

    if find_spec("nautilus_trader") is None:
        return NautilusRuntimeStatus(
            available=False,
            message=(
                "NautilusTrader is not installed; dry-run and contract validation "
                "remain available. Install the 'nautilus' extra before configuring "
                "a real broker adapter."
            ),
        )
    return NautilusRuntimeStatus(
        available=True,
        message="NautilusTrader package detected; no broker connection has been made.",
    )
