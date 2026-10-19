"""Inspect an explicit daily-data manifest without modifying its inputs."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

METADATA = {
    "market": {"HK", "US"},
    "source_state": {"synthetic", "archived_unverified", "owner_published"},
    "price_basis": {"raw", "adjusted", "unknown"},
    "universe_state": {"synthetic", "fixed_current", "point_in_time", "unknown"},
    "availability_state": {"verified", "period_only", "unknown"},
}
META_KEYS = set(METADATA) | {"producer", "dataset_id", "synthetic", "timezone"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("NONFINITE_JSON")


def _manifest(path: Path) -> tuple[dict, Path]:
    value = json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_unique,
        parse_constant=_reject_constant,
    )
    if (
        not isinstance(value, dict)
        or set(value) != META_KEYS | {"schema_version", "dataset_root", "files"}
        or value["schema_version"] != "competition.research_input_manifest.v1"
    ):
        raise ValueError("INVALID_MANIFEST")
    for key, allowed in METADATA.items():
        if not isinstance(value[key], str) or value[key] not in allowed:
            raise ValueError("INVALID_METADATA")
    if (
        type(value["synthetic"]) is not bool
        or value["synthetic"] != (value["source_state"] == "synthetic")
        or value["synthetic"] != (value["universe_state"] == "synthetic")
    ):
        raise ValueError("INVALID_SYNTHETIC_METADATA")
    if not isinstance(value["dataset_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value["dataset_id"]
    ):
        raise ValueError("INVALID_DATASET_ID")
    producer = value["producer"]
    if (
        not isinstance(producer, dict)
        or set(producer) != {"package", "package_version", "code_revision"}
        or producer["package"] != "competition-equity-lab"
        or producer["package_version"] != "0.1.0"
        or not isinstance(producer["code_revision"], str)
        or not re.fullmatch(r"unknown|[0-9a-f]{40}", producer["code_revision"])
    ):
        raise ValueError("INVALID_PRODUCER")
    zone = value["timezone"]
    if not isinstance(zone, str):
        raise ValueError("INVALID_TIMEZONE")
    if zone not in {
        "unknown",
        "UTC",
        "Etc/UTC",
        "Asia/Hong_Kong",
        "Asia/Shanghai",
        "America/New_York",
    }:
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("INVALID_TIMEZONE") from error
    if (
        not isinstance(value["dataset_root"], str)
        or not Path(value["dataset_root"]).is_absolute()
    ):
        raise ValueError("INVALID_DATASET_ROOT")
    root = Path(value["dataset_root"]).resolve(strict=True)
    if not root.is_dir() or not isinstance(value["files"], list) or not value["files"]:
        raise ValueError("EMPTY_FILES")
    return value, root


def _file(root: Path, item: dict, seen: set[Path]) -> Path:
    if not isinstance(item, dict) or set(item) != {
        "relative_path",
        "kind",
        "sha256",
        "size_bytes",
    }:
        raise ValueError("INVALID_FILE_FIELDS")
    ref = item["relative_path"]
    if not isinstance(ref, str) or not ref or ref.strip() != ref:
        raise ValueError("UNSAFE_FILE_REFERENCE")
    relative = PurePosixPath(ref)
    if (
        not relative.parts
        or relative.is_absolute()
        or relative.as_posix() != ref
        or ".." in relative.parts
        or "\\" in ref
        or ":" in ref
    ):
        raise ValueError("UNSAFE_FILE_REFERENCE")
    path = (root / ref).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or path in seen:
        raise ValueError("UNSAFE_FILE_REFERENCE")
    seen.add(path)
    if (
        not isinstance(item["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        or type(item["size_bytes"]) is not int
        or item["size_bytes"] < 0
    ):
        raise ValueError("INVALID_FILE_IDENTITY")
    if path.stat().st_size != item["size_bytes"] or _hash(path) != item["sha256"]:
        raise ValueError("FILE_CHANGED")
    return path


def _inspect(path: Path, market: str) -> tuple[int, set[tuple[str, str]]]:
    import numpy as np
    import pandas as pd

    from equity_lab.data.market_data import load_symbol_bars

    dates = pd.read_csv(path, usecols=["date"], dtype={"date": str})["date"]
    if not dates.map(
        lambda value: (
            isinstance(value, str)
            and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None
        )
    ).all():
        raise ValueError("INVALID_DAILY_DATE")
    frame = load_symbol_bars(path)
    if frame.empty:
        raise ValueError("EMPTY_MARKET_DATA")
    columns = ["open", "high", "low", "close", "volume"]
    values = frame[columns].apply(pd.to_numeric, errors="coerce")
    if (
        not np.isfinite(values.to_numpy()).all()
        or (values[["open", "high", "low", "close"]] <= 0).any().any()
        or (values["volume"] < 0).any()
    ):
        raise ValueError("INVALID_NUMERIC_DATA")
    if (values["high"] < values[["open", "close", "low"]].max(axis=1)).any() or (
        values["low"] > values[["open", "close", "high"]].min(axis=1)
    ).any():
        raise ValueError("INVALID_OHLC_BOUNDS")
    if (
        frame["date"].isna().any()
        or not frame["code"]
        .map(
            lambda code: (
                isinstance(code, str)
                and code.startswith(market + ".")
                and len(code) > len(market) + 1
            )
        )
        .all()
    ):
        raise ValueError("INVALID_INSTRUMENT_OR_DATE")
    keys = list(zip(frame["date"].astype(str), frame["code"], strict=True))
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATE_OBSERVATION")
    return len(frame), set(keys)


def validate_inputs(manifest_path: Path) -> dict:
    manifest, root = _manifest(manifest_path)
    files = []
    seen_files: set[Path] = set()
    seen_rows: set[tuple[str, str]] = set()
    for item in manifest["files"]:
        path = _file(root, item, seen_files)
        if item["kind"] != "daily_bars":
            raise ValueError("INVALID_FILE_KIND")
        rows, keys = _inspect(path, manifest["market"])
        if seen_rows & keys:
            raise ValueError("DUPLICATE_OBSERVATION")
        seen_rows.update(keys)
        if _hash(path) != item["sha256"]:
            raise ValueError("FILE_CHANGED_DURING_INSPECTION")
        files.append(item | {"rows": rows})
    value = {key: manifest[key] for key in META_KEYS}
    value.update(
        schema_version="competition.research_input_receipt.v1",
        files=files,
        quality={"issue_codes": []},
    )
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    value["fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = validate_inputs(args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"status": "inspected", "fingerprint": value["fingerprint"]}))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["INPUT_INSPECTION_FAILED"]}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
