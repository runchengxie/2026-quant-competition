"""Versioned, broker-neutral contracts exchanged with research systems."""

from .targets import Target, TargetSet, TargetValidationError

__all__ = ["Target", "TargetSet", "TargetValidationError"]
