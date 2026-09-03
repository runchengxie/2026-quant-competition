"""Resource guardrails for running inference beside IBKR Gateway on Windows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_workers: int = 2
    max_memory_gb: float = 8.0

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be positive")
        if self.max_memory_gb <= 0:
            raise ValueError("max_memory_gb must be positive")

    @classmethod
    def from_environment(cls) -> "ResourceBudget":
        workers = int(os.getenv("COMPETITION_COMPUTE_MAX_WORKERS", "2"))
        memory = float(os.getenv("COMPETITION_COMPUTE_MAX_MEMORY_GB", "8"))
        return cls(workers, memory)


class RunLock:
    """Cross-platform single-instance lock using exclusive file creation."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._handle: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._handle, f"pid={os.getpid()}\n".encode())
        except FileExistsError as exc:
            raise RuntimeError(f"run lock already held: {self.path}") from exc

    def release(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self) -> "RunLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
