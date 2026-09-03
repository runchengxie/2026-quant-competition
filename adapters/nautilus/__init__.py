"""Optional NautilusTrader runtime boundary.

No broker is imported or connected from this package.  Task 4 supplies the
IBKR adapter that will consume this boundary.
"""

from .runtime import NautilusRuntimeStatus, describe_nautilus_runtime

__all__ = ["NautilusRuntimeStatus", "describe_nautilus_runtime"]
