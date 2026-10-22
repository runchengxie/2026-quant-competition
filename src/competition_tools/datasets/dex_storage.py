"""Private immutable DEX dataset artifacts and independent byte verification."""

import json
import os
from datetime import datetime, timezone
from pathlib import PurePosixPath

from .dex_spec import safe_path, validate_dex_spec
from .dex_quality import UNITS, validate_hourly_rows
from .storage import digest, spec_hash, write_json

OWNER = "competition.dex_dataset.v1"


def read_json(path):
    def invalid(_):
        raise ValueError("NONFINITE_JSON")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)
    json.dumps(value, allow_nan=False)
    return value


def file_records(root):
    records = []
    for path in sorted(root.rglob("*")):
        safe_path(path)
        if path.is_file() and path.name not in {
            "manifest.json",
            ".dataset-owner",
            ".acquiring",
        }:
            relative = path.relative_to(root).as_posix()
            role = (
                "raw"
                if relative.startswith("raw/")
                else "normalized"
                if relative.startswith("normalized/")
                else "protocol"
                if relative == "protocol.json"
                else "receipt"
            )
            records.append(
                {
                    "path": relative,
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                    "role": role,
                }
            )
    return records


def write_dex_manifest(spec, staging, receipt):
    value = {
        "schema": "competition.dex_dataset_manifest.v1",
        "dataset_id": spec["dataset_id"],
        "version": spec["version"],
        "spec": spec,
        "spec_sha256": spec_hash(spec),
        "protocol_sha256": spec["protocol_sha256"],
        "status": receipt["status"],
        "units": UNITS,
        "files": file_records(staging),
        "coverage": receipt["coverage"],
        "snapshots": receipt["snapshots"],
        "budget": receipt["spent"],
        "availability": "bar_close_proxy_unverified",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "issues": receipt["issues"],
    }
    write_json(staging / "manifest.json", value)
    return value


def verify_dex_manifest(manifest_path):
    manifest_path = safe_path(manifest_path)
    value = read_json(manifest_path)
    if (
        not isinstance(value, dict)
        or value.get("schema") != "competition.dex_dataset_manifest.v1"
        or set(value)
        != {
            "schema",
            "dataset_id",
            "version",
            "spec",
            "spec_sha256",
            "protocol_sha256",
            "status",
            "units",
            "files",
            "coverage",
            "snapshots",
            "budget",
            "availability",
            "created_at",
            "issues",
        }
        or value.get("status") not in {"completed", "partial", "blocked"}
    ):
        raise ValueError("INVALID_DEX_MANIFEST")
    validate_dex_spec(value["spec"])
    if (
        value["spec_sha256"] != spec_hash(value["spec"])
        or value["protocol_sha256"] != value["spec"]["protocol_sha256"]
        or value["units"] != UNITS
        or value["dataset_id"] != value["spec"]["dataset_id"]
        or value["version"] != value["spec"]["version"]
        or value["availability"] != "bar_close_proxy_unverified"
    ):
        raise ValueError("INVALID_DEX_MANIFEST")
    root, seen = manifest_path.parent, set()
    for record in value["files"]:
        rel = PurePosixPath(record["path"])
        if (
            rel.is_absolute()
            or ".." in rel.parts
            or "\\" in str(rel)
            or str(rel) in seen
        ):
            raise ValueError("INVALID_MANIFEST_PATH")
        seen.add(str(rel))
        target = safe_path(root / rel)
        if (
            not target.is_relative_to(root)
            or not target.is_file()
            or target.stat().st_size != record["bytes"]
            or digest(target) != record["sha256"]
        ):
            raise ValueError("DATASET_HASH_MISMATCH")
    if value["files"] != file_records(root):
        raise ValueError("UNLISTED_DATASET_FILE")
    if digest(root / "protocol.json") != value["protocol_sha256"]:
        raise ValueError("PROTOCOL_HASH_MISMATCH")
    receipt = read_json(root / "receipt.json")
    if (
        receipt["status"] != value["status"]
        or receipt["coverage"] != value["coverage"]
        or receipt["spent"] != value["budget"]
        or receipt["issues"] != value["issues"]
        or receipt["snapshots"] != value["snapshots"]
        or receipt["spec_sha256"] != value["spec_sha256"]
    ):
        raise ValueError("INVALID_DEX_MANIFEST")
    return value


def inspect_dex(manifest_path):
    value = verify_dex_manifest(manifest_path)
    root, spec = safe_path(manifest_path).parent, value["spec"]
    coverage = []
    for asset in spec["assets"]:
        path = root / "normalized" / (asset["stable_id"] + ".json")
        rows = read_json(path) if path.exists() else []
        if any(row["asset_id"] != asset["stable_id"] for row in rows):
            raise ValueError("TOKEN_IDENTITY_MISMATCH")
        coverage.append(
            {
                "asset_id": asset["stable_id"],
                **validate_hourly_rows(
                    rows, start=spec["start"], end=spec["end"], units=UNITS
                ),
            }
        )
    if coverage != value["coverage"]:
        raise ValueError("COVERAGE_MISMATCH")
    return {
        "schema": "competition.dex_coverage.v1",
        "status": value["status"],
        "verification": "verified",
        "assets": coverage,
        "manifest_sha256": digest(safe_path(manifest_path)),
    }


def publish_dex(staging, destination):
    staging, destination = safe_path(staging), safe_path(destination)
    if destination.exists():
        raise FileExistsError("DATASET_VERSION_EXISTS")
    if (staging / ".dataset-owner").read_text() != OWNER:
        raise ValueError("UNOWNED_STAGING")
    value = verify_dex_manifest(staging / "manifest.json")
    if value["status"] not in {"completed", "partial"}:
        raise ValueError("BLOCKED_DATASET_NOT_PUBLISHABLE")
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
    return value
