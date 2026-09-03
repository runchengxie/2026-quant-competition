"""Nira target handoff without importing the Nira research implementation."""

from .handoff import (
    HandoffValidationError,
    NiraTargetHandoff,
    load_target_artifact,
    write_target_artifact,
)

__all__ = [
    "HandoffValidationError",
    "NiraTargetHandoff",
    "load_target_artifact",
    "write_target_artifact",
]
