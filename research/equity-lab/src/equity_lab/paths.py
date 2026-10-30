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
    return project_root(root, settings.get("project_data_root")) / "research" / "equity-lab"

PROJECT_ROOT = load_data_root()
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
DATA_ROOT = ARTIFACTS_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
INTERIM_ROOT = DATA_ROOT / "interim"
PROCESSED_ROOT = DATA_ROOT / "processed"
REPORTS_ROOT = ARTIFACTS_ROOT / "reports"
BACKTEST_REPORTS_ROOT = REPORTS_ROOT / "backtests"
DAILY_REPORTS_ROOT = REPORTS_ROOT / "daily"
TARGETS_ROOT = REPORTS_ROOT / "targets"
LOGS_ROOT = ARTIFACTS_ROOT / "logs"
