"""External experiment destinations independent of maintainer configuration."""

from pathlib import Path


def external_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        raise ValueError("ABSOLUTE_PATH_REQUIRED")
    path = path.resolve()
    if any(
        (parent / ".git").exists() or parent.name == ".git"
        for parent in (path, *path.parents)
    ):
        raise ValueError("OUTPUT_IN_SOURCE")
    return path
