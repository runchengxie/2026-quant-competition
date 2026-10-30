"""Resolve permanent project data from machine-local workspace settings."""

import os
from pathlib import Path
import tomllib

from ._project_storage import project_root


def load_data_root() -> Path:
    """Return this project's raw data directory, independent of its checkout."""
    data_root = os.environ.get("DATA_ROOT")
    settings = {}
    if data_root is None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        config_root = Path(os.environ.get("CONFIG_ROOT", config_home / "quant-competition"))
        config_file = Path(os.environ.get(
            "WORKSPACE_CONFIG", config_root / "shared" / "workspace.toml"
        )).expanduser()
        try:
            with config_file.open("rb") as stream:
                settings = tomllib.load(stream)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid workspace TOML in {config_file}: {exc}") from exc
        except OSError as exc:
            raise ValueError(
                f"Cannot read workspace configuration {config_file}. "
                "Set WORKSPACE_CONFIG to a readable workspace.toml file "
                "or DATA_ROOT to an absolute data directory."
            ) from exc
        data_root = settings.get("data_root")

    if not isinstance(data_root, str) or not data_root.strip():
        raise ValueError("data_root / DATA_ROOT must be a non-empty absolute path")
    root = Path(data_root).expanduser()
    if not root.is_absolute():
        raise ValueError("data_root / DATA_ROOT must be an absolute path")
    # The permanent owner is fixed; a task worktree name must never select data.
    return project_root(root, settings.get("project_data_root")) / "research" / "crypto-mm" / "raw_data"
