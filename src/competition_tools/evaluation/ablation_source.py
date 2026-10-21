"""Retain committed source bytes without local metadata or untracked files."""

import io
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest
from .study_identity import source_hash


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30
    ).stdout


def snapshot_source(source_root: Path, output_root: Path) -> dict:
    root = Path(source_root).expanduser()
    if not root.is_absolute() or any(
        p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
        for p in (root, *root.parents)
    ):
        raise ValueError("INVALID_SOURCE_ROOT")
    root = root.resolve()
    relevant = [
        "src",
        "research/equity-lab/src",
        "research/crypto-mm/src",
        "pyproject.toml",
        "uv.lock",
        "research/equity-lab/pyproject.toml",
        "research/equity-lab/uv.lock",
        "research/crypto-mm/pyproject.toml",
        "research/crypto-mm/uv.lock",
    ]
    if _git(
        root, "status", "--porcelain", "--untracked-files=all", "--", *relevant
    ).strip():
        raise ValueError("DIRTY_ABLATION_SOURCE")
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    expected = source_hash(root)
    archive = _git(root, "archive", "--format=zip", "HEAD")
    out = safe_path(output_root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "source.zip").write_bytes(archive)
    tree = out / "source"
    tree.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for member in z.infolist():
            rel = PurePosixPath(member.filename)
            if (
                rel.is_absolute()
                or ".." in rel.parts
                or chr(92) in member.orig_filename
                or ":" in member.filename
                or (member.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("UNSAFE_SOURCE_ARCHIVE")
            target = tree / rel
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(member))
    if source_hash(tree) != expected:
        raise ValueError("SOURCE_SNAPSHOT_MISMATCH")
    receipt = {
        "commit": commit,
        "source_root": str(tree.resolve()),
        "source_sha256": expected,
        "archive": str((out / "source.zip").resolve()),
        "archive_sha256": digest(out / "source.zip"),
    }
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return verify_source_snapshot(receipt)


def verify_source_snapshot(receipt: dict) -> dict:
    if set(receipt) != {
        "commit",
        "source_root",
        "source_sha256",
        "archive",
        "archive_sha256",
    }:
        raise ValueError("INVALID_SOURCE_RECEIPT")
    if (
        digest(safe_path(Path(receipt["archive"]))) != receipt["archive_sha256"]
        or source_hash(safe_path(Path(receipt["source_root"])))
        != receipt["source_sha256"]
    ):
        raise ValueError("SOURCE_SNAPSHOT_CHANGED")
    return receipt
