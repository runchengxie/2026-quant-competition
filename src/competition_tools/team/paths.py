"""Validate external destinations, including linked Git worktrees."""

from pathlib import Path


def validate_external(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise ValueError("An absolute external path is required")
    resolved = expanded.resolve()
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists() or parent.name == ".git":
            raise ValueError("Source repository destinations are forbidden")
        if parent != resolved and parent.exists() and not parent.is_dir():
            raise ValueError("A destination parent is not a directory")
    return resolved
