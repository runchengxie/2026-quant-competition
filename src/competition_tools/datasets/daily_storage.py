"""Owned immutable daily snapshots and verified relative payload files."""

import json
from pathlib import Path, PurePosixPath

from competition_tools import gateway_launcher as gl
from competition_tools.team.paths import validate_external
from .storage import digest, spec_hash, write_json
from .daily_spec import validate_daily_spec

OWNER = "competition.dataset.v2"


def safe_path(path: Path) -> Path:
    # Check before resolve: resolving first loses symlink/junction evidence.
    gl._path(str(path), exists=False, shell_path=False)
    return validate_external(path)


def payload_files(root: Path) -> list[dict]:
    files = []
    for directory in ("raw", "normalized"):
        for path in sorted((root / directory).glob("*")):
            safe_path(path)
            if not path.is_file():
                raise ValueError("INVALID_PAYLOAD_PATH")
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                }
            )
    return files


def verify_files(root: Path, records: list[dict]) -> None:
    if not isinstance(records, list):
        raise ValueError("INVALID_MANIFEST_FILES")
    seen = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "bytes"}
            or not isinstance(record["path"], str)
        ):
            raise ValueError("INVALID_MANIFEST_FILE")
        relative = PurePosixPath(record["path"])
        if (
            len(relative.parts) != 2
            or relative.parts[0] not in {"raw", "normalized"}
            or ".." in relative.parts
            or "\\" in record["path"]
            or ":" in record["path"]
            or record["path"] in seen
        ):
            raise ValueError("INVALID_MANIFEST_PATH")
        seen.add(record["path"])
        path = safe_path(root / relative)
        if (
            not path.is_file()
            or type(record["bytes"]) is not int
            or path.stat().st_size != record["bytes"]
            or digest(path) != record["sha256"]
        ):
            raise ValueError("DATASET_HASH_MISMATCH")
    if {f["path"] for f in payload_files(root)} != seen:
        raise ValueError("UNRECORDED_PAYLOAD")


def write_daily_manifest(
    spec: dict, staging: Path, receipt: dict, *, parent_sha256: str | None = None
) -> dict:
    validate_daily_spec(spec)
    staging = safe_path(staging)
    if (staging / ".dataset-owner").read_text() != OWNER:
        raise ValueError("UNOWNED_STAGING")
    destination = staging / "manifest.json"
    if destination.exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    if receipt["spec_hash"] != spec_hash(spec):
        raise ValueError("SPEC_HASH_MISMATCH")
    files = payload_files(staging)
    value = {
        "schema": "competition.dataset_manifest.v2",
        "dataset_id": spec["dataset_id"],
        "version": spec["version"],
        "spec_hash": spec_hash(spec),
        "spec": {k: v for k, v in spec.items() if k != "connection_file"},
        "receipt": receipt,
        "observed_at": receipt["observed_at"],
        "status": receipt["status"],
        "coverage": receipt["coverage"],
        "gaps": receipt["gaps"],
        "files": files,
        "parent_manifest_sha256": parent_sha256,
        "accepted_research": False,
    }
    write_json(destination, value)
    return value


def verify_daily_manifest(path: Path) -> dict:
    path = safe_path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != "competition.dataset_manifest.v2"
        or value.get("accepted_research") is not False
    ):
        raise ValueError("INVALID_DAILY_MANIFEST")
    if (path.parent / ".dataset-owner").read_text() != OWNER:
        raise ValueError("UNOWNED_DATASET")
    verify_files(path.parent, value["files"])
    receipt = json.loads((path.parent / "receipt.json").read_text(encoding="utf-8"))
    if receipt != value["receipt"] or any(
        value[k] != receipt[k] for k in ("spec_hash", "status", "coverage", "gaps")
    ):
        raise ValueError("RECEIPT_MISMATCH")
    if receipt["retained_payload_bytes"] != sum(f["bytes"] for f in value["files"]):
        raise ValueError("PAYLOAD_SIZE_MISMATCH")
    return value
