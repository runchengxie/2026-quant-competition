"""Offline completed-layout manifest and explicit verified local/mounted copy.

Never starts conversion, SSH, a watcher, or a shared-data pointer update.
"""

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe(root, relative):
    relative = relative.replace("\\", "/")
    parts = PurePosixPath(relative).parts
    if not parts or ".." in parts or ":" in relative or relative.startswith("/"):
        raise ValueError("Unsafe manifest path")
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError("Escaping or linked manifest path")
    return path


def build_manifest(source):
    root = Path(source).resolve(strict=True)
    progress = json.loads((root / "progress.json").read_text(encoding="utf-8-sig"))
    if progress.get("status") != "complete" or progress.get("phase") != "complete":
        raise ValueError("Source conversion is not complete")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8-sig"))
    checks = [
        "all_columns_logical_sha256_readback_both_stages",
        "input_file_sha256_verified",
        "all_parquet_pages_checksum_verified",
        "source_manifest_unchanged",
        "strict_per_security_year_time_order",
    ]
    if (
        summary.get("status") != "complete"
        or summary.get("scope") != "full"
        or any(summary.get(k) is not True for k in checks)
    ):
        raise ValueError("Final verification receipts incomplete")
    rows = list(
        csv.DictReader((root / "file_index.csv").open(encoding="utf-8-sig", newline=""))
    )
    if (
        not rows
        or sum(int(r["rows"]) for r in rows) != summary["rows"]
        or sum(int(r["volume"]) for r in rows) != summary["volume"]
    ):
        raise ValueError("Row/volume conservation failed")
    if (
        len(rows) != summary["parts"]
        or progress.get("final_verified_rows") != summary["rows"]
        or progress.get("expected_rows") != summary["rows"]
    ):
        raise ValueError("Final part/progress conservation failed")
    files = []
    for row in rows:
        relative = row["file"].replace("\\", "/")
        if not relative.startswith("parquet/"):
            raise ValueError("Only final parquet paths are eligible")
        path = _safe(root, relative)
        digest = _digest(path)
        if digest != row["sha256"] or path.stat().st_size != int(row["bytes"]):
            raise ValueError("Final file changed since verification")
        files.append({"path": relative, "size": path.stat().st_size, "sha256": digest})
    if len({item["path"] for item in files}) != len(files):
        raise ValueError("Duplicate final path")
    for name in [
        "summary.json",
        "progress.json",
        "file_index.csv",
        "run_config.json",
        "README.txt",
    ]:
        path = root / name
        if path.exists():
            files.append(
                {"path": name, "size": path.stat().st_size, "sha256": _digest(path)}
            )
    return {
        "schema_version": 1,
        "source": str(root),
        "rows": summary["rows"],
        "volume": summary["volume"],
        "files": files,
        "total_bytes": sum(r["size"] for r in files),
        "excluded": ["staging", "work", "recovery", "catalog.duckdb"],
        "note": "Catalog embeds original paths; rebuild separately at destination. Original archive needs its own frozen manifest.",
    }


def verify_manifest(manifest):
    root = Path(manifest["source"]).resolve(strict=True)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest version")
    for item in manifest["files"]:
        path = _safe(root, item["path"])
        if path.stat().st_size != item["size"] or _digest(path) != item["sha256"]:
            raise ValueError("Manifest source changed")


def copy_manifest(manifest, destination):
    verify_manifest(manifest)
    destination = Path(destination).resolve()
    source = Path(manifest["source"]).resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Destination overlaps source")
    staging = destination.with_name(destination.name + ".partial")
    if destination.exists() or staging.exists():
        raise FileExistsError(
            "Destination or partial already exists; review before retry"
        )
    if shutil.disk_usage(destination.parent).free < manifest["total_bytes"] * 1.1:
        raise ValueError("Insufficient free space including 10 percent headroom")
    staging.mkdir()
    for item in manifest["files"]:
        source_path = _safe(source, item["path"])
        target = _safe(staging.resolve(), item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        if target.stat().st_size != item["size"] or _digest(target) != item["sha256"]:
            raise ValueError("Copied file verification failed")
    verify_manifest(manifest)
    (staging / "transfer-receipt.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    staging.rename(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Freeze a complete final-layout manifest, optionally copy to a mounted destination"
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output", required=True, type=Path, help="New private manifest file"
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Explicit new dated destination; no remote transport or pointer switch",
    )
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.source)
        if args.output.resolve().is_relative_to(args.source.resolve()):
            raise ValueError("Manifest output must be outside source")
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
        if args.copy_to:
            copy_manifest(manifest, args.copy_to)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Handoff blocked: {error}\n")
    print(
        "Verified handoff copied"
        if args.copy_to
        else "Manifest prepared; no data copied"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
