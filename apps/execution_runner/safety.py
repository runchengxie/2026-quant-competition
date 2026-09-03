from __future__ import annotations

import os
from pathlib import Path


class KillSwitch:
    """Filesystem kill switch checked before any broker submission."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    @property
    def is_triggered(self) -> bool:
        return self.path.exists()

    def assert_clear(self) -> None:
        if self.is_triggered:
            raise RuntimeError(f"kill switch is active: {self.path}")

    def trigger(self, reason: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(reason + "\n", encoding="utf-8")
