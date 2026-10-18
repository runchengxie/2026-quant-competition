from __future__ import annotations

from pathlib import Path


def load_universe_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
