"""Nira target handoff without importing the Nira research implementation."""

from .handoff import (
    HandoffValidationError,
    NiraTargetHandoff,
    load_target_artifact,
    write_target_artifact,
)
from .audit import AlignmentAudit, audit_forward_alignment

__all__ = [
    "HandoffValidationError",
    "NiraTargetHandoff",
    "load_target_artifact",
    "write_target_artifact",
    "AlignmentAudit",
    "audit_forward_alignment",
]
