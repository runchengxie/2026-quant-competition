"""Retain committed source with the exact newline bytes used by the interpreter."""

import subprocess
import zipfile
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ..study_identity import source_hash


def snapshot_source(source_root: Path, output_root: Path) -> dict:
    root = Path(source_root).absolute()
    if any(
        p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
        for p in (root, *root.parents)
    ):
        raise ValueError("CONTROLS_SOURCE_REPARSE")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30
        ).stdout

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
    if git("status", "--porcelain", "--untracked-files=all", "--", *relevant).strip():
        raise ValueError("DIRTY_CONTROLS_SOURCE")
    out = safe_path(output_root)
    out.mkdir(parents=True, exist_ok=False)
    expected = source_hash(root)
    tree = out / "source"
    tree.mkdir()
    with zipfile.ZipFile(out / "source.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for name in git("ls-files", "-z").decode("utf-8").split("\0"):
            if not name:
                continue
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("UNSAFE_CONTROLS_SOURCE")
            body = path.read_bytes()
            archive.writestr(name, body)
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    if source_hash(tree) != expected or source_hash(root) != expected:
        raise ValueError("CONTROLS_SOURCE_CHANGED")
    receipt = dict(
        commit=git("rev-parse", "HEAD").decode().strip(),
        source_root=str(tree),
        source_sha256=expected,
        archive=str(out / "source.zip"),
        archive_sha256=digest(out / "source.zip"),
    )
    write_json(out / "receipt.json", receipt)
    return receipt
