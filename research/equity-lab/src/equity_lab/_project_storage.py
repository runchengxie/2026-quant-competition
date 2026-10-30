"""Explicit project locations; relocation never changes research identities."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re


LEGACY = "2026-quant-competition"
CANONICAL = "global-market-research"
ENVIRONMENT = "GLOBAL_MARKET_RESEARCH_DATA_ROOT"


def _checked(value):
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError("INVALID_PROJECT_PATH")
    path = Path(value).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("INVALID_PROJECT_PATH")
    for parent in (path, *path.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("PROJECT_REPARSE_PATH")
        if (parent / ".git").exists() or parent.name == ".git":
            raise ValueError("PROJECT_PATH_IN_SOURCE")
    return path.resolve()


def project_root(data_root, explicit=None):
    """Select legacy-only, canonical-only or a fresh canonical installation."""
    base = _checked(data_root)
    old, new = _checked(base / LEGACY), _checked(base / CANONICAL)
    selected = explicit if explicit is not None else os.environ.get(ENVIRONMENT)
    if selected is not None:
        root = _checked(selected)
        if root not in (old, new):
            raise ValueError("INVALID_PROJECT_DATA_ROOT")
    else:
        if old.exists() and new.exists():
            raise ValueError("AMBIGUOUS_PROJECT_DATA_ROOT")
        root = old if old.exists() else new
    if root.exists() and not root.is_dir():
        raise ValueError("PROJECT_DATA_ROOT_NOT_DIRECTORY")
    return root


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("DUPLICATE_MIGRATION_FIELD")
        value[key] = item
    return value


def relocated_path(value):
    """Map a known location field only with an exact completed-move receipt."""
    path = _checked(value)
    owners = [p for p in (path, *path.parents) if p.name == LEGACY]
    if not owners:
        return path
    for old in owners:
        new = _checked(old.parent / CANONICAL)
        receipt = _checked(new / ".storage-migration.json")
        if old.exists() or not receipt.is_file():
            continue
        record = json.loads(
            receipt.read_text(encoding="utf-8"), object_pairs_hook=_pairs
        )
        if (
            not isinstance(record, dict)
            or set(record)
            != {"schema", "legacy_root", "canonical_root", "phase", "inventory_sha256"}
            or record["schema"] != "competition.storage_migration.v1"
            or record["phase"] != "completed"
            or _checked(record["legacy_root"]) != old
            or _checked(record["canonical_root"]) != new
            or not isinstance(record["inventory_sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", record["inventory_sha256"]) is None
        ):
            raise ValueError("INVALID_STORAGE_MIGRATION_RECEIPT")
        return _checked(new / path.relative_to(old))
    return path


def alternate_locations(owner, relative):
    """Enumerate possible consumed markers without assuming a second authority."""
    owner = _checked(owner)
    name = PurePosixPath(relative)
    if (
        not isinstance(relative, str)
        or str(name) != relative
        or name.is_absolute()
        or not name.parts
        or ".." in name.parts
        or "\\" in relative
        or ":" in relative
    ):
        raise ValueError("INVALID_GUARD_LOCATION")
    roots = [owner]
    project = _enclosing_project(owner)
    if project is not None:
        roots += [
            project.parent / n / owner.relative_to(project)
            for n in (LEGACY, CANONICAL)
            if n != project.name
        ]
    return [_checked(root / name) for root in roots]


def _enclosing_project(owner):
    return next(
        (p for p in (owner, *owner.parents) if p.name in (LEGACY, CANONICAL)), None
    )


@contextmanager
def guarded_location(owner, relative):
    """Serialize aliases and reject any existing durable attempt/reservation."""
    owner = _checked(owner)
    paths = alternate_locations(owner, relative)
    project = _enclosing_project(owner)
    namespace = (
        CANONICAL + ":" + owner.relative_to(project).as_posix()
        if project is not None
        else str(owner)
    )
    token = hashlib.sha256((namespace + ":" + relative).encode()).hexdigest()
    # A sibling lock survives root selection/move; it is not a research receipt.
    locks = _checked(
        (project.parent if project is not None else owner.parent)
        / ".global-market-research-guards"
    )
    locks.mkdir(parents=True, exist_ok=True)
    lock = locks / (token + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if any(p.exists() or Path(str(p) + ".started").exists() for p in paths):
            raise FileExistsError("PROJECT_ATTEMPT_ALREADY_RESERVED")
        yield paths[0]
    finally:
        os.close(fd)
        lock.unlink()
