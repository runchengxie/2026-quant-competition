"""Independent factor protocol and immutable producer-artifact checks."""

import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path, PurePosixPath

from .signals import SIGNALS, hour, grid


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("NONFINITE_JSON")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=invalid,
    )
    json.dumps(value, allow_nan=False)
    return value


def external(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.anchor.startswith("\\\\"):
        raise ValueError("INVALID_FACTOR_PATH")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("FACTOR_REPARSE_PATH")
        if (part / ".git").exists():
            raise ValueError("FACTOR_PATH_INSIDE_SOURCE")
    return path.resolve()


def validate_factor_protocol(value):
    try:
        constants = dict(
            schema="competition.dex_factor_protocol.v1",
            signals=SIGNALS,
            horizons=[6, 24],
            sampling=["all_valid", "non_overlapping"],
            role="retrospective",
            parameter_search=False,
            minimum_overall=30,
            minimum_slice=20,
            slices=3,
            slice_hours=720,
            groups=3,
            minimum_underlyings=9,
            minimum_per_group=3,
            availability="bar_close_proxy_unverified",
        )
        if not isinstance(value, dict) or set(value) != set(constants) | {
            "dataset",
            "manifest_file",
            "source_commit",
            "source_files",
        }:
            raise ValueError
        for key, expected in constants.items():
            if type(value[key]) is not type(expected) or value[key] != expected:
                raise ValueError
        if not re.fullmatch("[a-f0-9]{40}", value["source_commit"]):
            raise ValueError
        external(value["manifest_file"])
        dataset = value["dataset"]
        if set(dataset) != {
            "dataset_id",
            "version",
            "source",
            "interval",
            "quote_currency",
            "selection",
            "start",
            "end",
            "assets",
        }:
            raise ValueError
        if any(
            dataset[k] != v
            for k, v in dict(
                source="dexpaprika",
                interval="1h",
                quote_currency="USD",
                selection="fixed_current",
            ).items()
        ):
            raise ValueError
        if hour(dataset["end"]) - hour(dataset["start"]) != timedelta(days=90):
            raise ValueError
        for key in ("dataset_id", "version"):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", dataset[key]):
                raise ValueError
        assets = dataset["assets"]
        if not isinstance(assets, list) or not 1 <= len(assets) <= 10:
            raise ValueError
        seen = [set(), set(), set()]
        for asset in assets:
            if not {"stable_id", "underlying_id", "network", "address"} <= set(
                asset
            ) or set(asset) - {
                "stable_id",
                "underlying_id",
                "network",
                "address",
                "pool_address",
            }:
                raise ValueError
            if any(
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", asset[k])
                for k in ("stable_id", "underlying_id")
            ):
                raise ValueError
            pattern = (
                r"0x[0-9a-f]{40}"
                if asset["network"] == "ethereum"
                else r"[1-9A-HJ-NP-Za-km-z]{32,44}"
                if asset["network"] == "solana"
                else None
            )
            if (
                not pattern
                or not re.fullmatch(pattern, asset["address"])
                or (
                    "pool_address" in asset
                    and not re.fullmatch(pattern, asset["pool_address"])
                )
            ):
                raise ValueError
            for values, identity in zip(
                seen,
                (
                    asset["stable_id"],
                    asset["underlying_id"],
                    (asset["network"], asset["address"]),
                ),
                strict=True,
            ):
                if identity in values:
                    raise ValueError
                values.add(identity)
        files = value["source_files"]
        package = Path(__file__).resolve().parent.parent
        expected = {
            p.relative_to(package).as_posix()
            for p in (package / "factors").glob("*.py")
        }
        if (
            not isinstance(files, list)
            or len(files) != len(expected)
            or {f["path"] for f in files} != expected
        ):
            raise ValueError
        if any(
            set(f) != {"path", "sha256"}
            or not re.fullmatch("[a-f0-9]{64}", f["sha256"])
            for f in files
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("INVALID_FACTOR_PROTOCOL") from None


def verify_inputs(protocol):
    validate_factor_protocol(protocol)
    package = Path(__file__).resolve().parent.parent
    code_hashes = {}
    for record in protocol["source_files"]:
        path = package / record["path"]
        if path.is_symlink() or file_hash(path) != record["sha256"]:
            raise ValueError("FACTOR_SOURCE_MISMATCH")
        code_hashes[record["path"]] = record["sha256"]
    manifest_path = external(protocol["manifest_file"])
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema") != "competition.dex_dataset_manifest.v1"
        or set(manifest)
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
        or manifest.get("units") != {"price": "USD", "volume": "USD"}
        or manifest.get("status") not in {"completed", "partial", "blocked"}
        or manifest.get("availability") != "bar_close_proxy_unverified"
    ):
        raise ValueError("INVALID_FACTOR_MANIFEST")
    dataset = protocol["dataset"]
    expected_spec_hash = hashlib.sha256(
        json.dumps(manifest["spec"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        manifest["spec_sha256"] != expected_spec_hash
        or manifest["spec"].get("schema") != "competition.dex_dataset_spec.v1"
        or manifest["spec"].get("protocol_sha256") != manifest["protocol_sha256"]
    ):
        raise ValueError("INVALID_FACTOR_MANIFEST")
    if {k: manifest["spec"].get(k) for k in dataset} != dataset:
        raise ValueError("FACTOR_DATASET_MISMATCH")
    root, hashes, seen = manifest_path.parent, {}, set()
    rows = {a["stable_id"]: [] for a in dataset["assets"]}
    for record in manifest["files"]:
        if set(record) != {"path", "sha256", "bytes", "role"} or record["role"] not in {
            "raw",
            "normalized",
            "snapshot",
            "protocol",
            "receipt",
        }:
            raise ValueError("INVALID_FACTOR_MANIFEST")
        relative = PurePosixPath(record["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in str(relative)
            or str(relative) in seen
            or type(record["bytes"]) is not int
        ):
            raise ValueError("INVALID_FACTOR_MANIFEST_PATH")
        path = external(root / relative)
        if (
            not path.is_relative_to(root)
            or path.stat().st_size != record["bytes"]
            or file_hash(path) != record["sha256"]
        ):
            raise ValueError("FACTOR_INPUT_HASH_MISMATCH")
        seen.add(str(relative))
        hashes[str(relative)] = record["sha256"]
        if record["role"] == "normalized":
            data = read_json(path)
            if not isinstance(data, list):
                raise ValueError("INVALID_FACTOR_CANDLES")
            for row in data:
                if row["asset_id"] not in rows:
                    raise ValueError("UNKNOWN_FACTOR_ASSET")
                rows[row["asset_id"]].append(row)
    copied = external(root / "protocol.json")
    if (
        file_hash(copied) != manifest["protocol_sha256"]
        or read_json(copied) != protocol
    ):
        raise ValueError("FACTOR_PROTOCOL_HASH_MISMATCH")
    for bars in rows.values():
        grid(bars)
        if any(
            not hour(dataset["start"]) <= hour(r["time_open"]) < hour(dataset["end"])
            for r in bars
        ):
            raise ValueError("FACTOR_CANDLE_OUTSIDE_RANGE")
    return {
        "rows": rows,
        "manifest": manifest,
        "manifest_sha256": file_hash(manifest_path),
        "protocol_sha256": file_hash(copied),
        "input_hashes": hashes,
        "code_hashes": code_hashes,
    }
