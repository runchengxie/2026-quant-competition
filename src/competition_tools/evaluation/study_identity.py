"""Deterministic source identity for the independently installed study CLIs."""

import hashlib
import json
import subprocess
from pathlib import Path


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def tree_hash(root: Path) -> str:
    if not root.is_dir():
        raise ValueError("SOURCE_ROOT_REQUIRED")
    records = []
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink() or any(
            p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
            for p in path.parents
            if p != root.parent
        ):
            raise ValueError("SOURCE_REPARSE_PATH")
        records.append(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return canonical_hash(records)


def source_hash(root: Path) -> str:
    roots = ["src", "research/equity-lab/src", "research/crypto-mm/src"]
    files = [
        root / directory / name
        for directory in (".", "research/equity-lab", "research/crypto-mm")
        for name in ("pyproject.toml", "uv.lock")
    ]
    metadata = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
        if p.is_file()
    }
    return canonical_hash(
        {"trees": {r: tree_hash(root / r) for r in roots}, "metadata": metadata}
    )


def source_identity(root: Path) -> dict:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise ValueError("STUDY_SOURCE_CHECKOUT_REQUIRED") from None
    return {
        "commit": result.stdout.strip(),
        "source_root": str(root.resolve()),
        "source_sha256": source_hash(root),
    }
