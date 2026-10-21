"""Exclusive publication and byte-level verification of external datasets."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from competition_tools.team.paths import validate_external
from .spec import validate_spec


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: dict) -> None:
    body = json.dumps(value, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".checkpoint-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def publish_dataset(spec: dict, staging: Path, destination: Path) -> dict:
    validate_spec(spec)
    staging, destination = validate_external(staging), validate_external(destination)
    if destination.exists():
        raise FileExistsError("DATASET_VERSION_EXISTS")
    manifest = write_manifest(spec, staging)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name(destination.name + ".publish-lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        if destination.exists():
            raise FileExistsError("DATASET_VERSION_EXISTS")
        staging.rename(destination)
    finally:
        os.close(fd)
        lock.unlink()
    return manifest


def write_manifest(spec: dict, staging: Path) -> dict:
    validate_spec(spec)
    staging = validate_external(staging)
    if (staging / ".dataset-owner").read_text() != "competition.dataset.v1":
        raise ValueError("UNOWNED_STAGING")
    files = []
    for path in sorted(staging.rglob("*")):
        if path.is_symlink():
            raise ValueError("DATASET_SYMLINK")
        if path.is_file() and path.name not in {"manifest.json", ".dataset-owner"}:
            files.append(
                {
                    "path": path.relative_to(staging).as_posix(),
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                }
            )
    receipt = (
        json.loads((staging / "receipt.json").read_text())
        if (staging / "receipt.json").exists()
        else {}
    )
    public_spec = {
        k: v
        for k, v in spec.items()
        if k
        not in {"credential_file", "input_directory", "membership_file", "contracts"}
    }
    manifest = {
        "schema": "competition.dataset_manifest.v1",
        "dataset_id": spec["dataset_id"],
        "version": spec["version"],
        "spec_hash": spec_hash(spec),
        "spec": public_spec,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "available_at": None,
        "status": receipt.get("status", "partial"),
        "coverage": receipt.get("coverage", {}),
        "gaps": receipt.get("gaps", []),
        "files": files,
        "accepted_research": False,
    }
    write_json(staging / "manifest.json", manifest)
    return manifest


def verify_manifest(manifest_path: Path) -> dict:
    original_manifest_path = manifest_path
    manifest_path = validate_external(manifest_path)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value.get("schema") == "competition.dataset_manifest.v2":
        from .daily_storage import verify_daily_manifest
        return verify_daily_manifest(original_manifest_path)
    if value.get("schema") != "competition.dataset_manifest.v1":
        raise ValueError("INVALID_MANIFEST")
    root = manifest_path.parent.resolve()
    for record in value["files"]:
        relative = PurePosixPath(record["path"])
        target = root / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not target.resolve().is_relative_to(root)
            or target.is_symlink()
        ):
            raise ValueError("INVALID_MANIFEST_PATH")
        if (
            not target.is_file()
            or target.stat().st_size != record["bytes"]
            or digest(target) != record["sha256"]
        ):
            raise ValueError("DATASET_HASH_MISMATCH")
    return value
