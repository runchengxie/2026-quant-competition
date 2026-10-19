"""Inspect exact-byte research input receipts without attesting vendor claims."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = "competition.research_input_receipt.v1"
METADATA_ENUMS = {
    "market": {"HK", "US", "CRYPTO"},
    "source_state": {"synthetic", "archived_unverified", "owner_published"},
    "price_basis": {"raw", "adjusted", "unknown"},
    "universe_state": {"synthetic", "fixed_current", "point_in_time", "unknown"},
    "availability_state": {"verified", "period_only", "unknown"},
}
KINDS = {"daily_bars", "orderbook", "trades", "fundings"}
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"[A-Z][A-Z0-9_]*\Z")
KEYS = {
    "schema_version",
    "producer",
    "dataset_id",
    "synthetic",
    "timezone",
    "files",
    "quality",
    "fingerprint",
} | set(METADATA_ENUMS)


def _mapping(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("INVALID_FIELDS")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("INVALID_TEXT")
    return value


def _count(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("INVALID_COUNT")


def _digest(value: object) -> None:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError("INVALID_DIGEST")


def relative_reference(value: object) -> str:
    text = _text(value)
    path = PurePosixPath(text)
    if (
        not path.parts
        or path.is_absolute()
        or path.as_posix() != text
        or any(part in {".", ".."} for part in path.parts)
        or "\\" in text
        or ":" in text
    ):
        raise ValueError("UNSAFE_FILE_REFERENCE")
    return text


def receipt_fingerprint(payload: dict) -> str:
    values = {key: value for key, value in payload.items() if key != "fingerprint"}
    try:
        encoded = json.dumps(
            values,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("INVALID_JSON_VALUE") from error
    return hashlib.sha256(encoded).hexdigest()


def validate_input_receipt(payload: object) -> dict:
    value = _mapping(payload, KEYS)
    if value["schema_version"] != SCHEMA:
        raise ValueError("UNSUPPORTED_SCHEMA")
    producer = _mapping(
        value["producer"], {"package", "package_version", "code_revision"}
    )
    for item in producer.values():
        _text(item)
    revision = producer["code_revision"]
    if revision != "unknown" and not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("INVALID_PRODUCER_REVISION")
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", _text(value["dataset_id"])
    ):
        raise ValueError("INVALID_DATASET_ID")
    for key, allowed in METADATA_ENUMS.items():
        if not isinstance(value[key], str) or value[key] not in allowed:
            raise ValueError("INVALID_METADATA")
    if type(value["synthetic"]) is not bool:
        raise ValueError("INVALID_SYNTHETIC_FLAG")
    if value["synthetic"] != (value["source_state"] == "synthetic") or value[
        "synthetic"
    ] != (value["universe_state"] == "synthetic"):
        raise ValueError("INCONSISTENT_SYNTHETIC_METADATA")
    timezone = _text(value["timezone"])
    # Standard market zones remain usable on Windows without a system tz database.
    if timezone not in {
        "unknown",
        "UTC",
        "Etc/UTC",
        "Asia/Hong_Kong",
        "Asia/Shanghai",
        "America/New_York",
    }:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("INVALID_TIMEZONE") from error
    files = value["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("EMPTY_FILES")
    seen = set()
    for item in files:
        item = _mapping(item, {"relative_path", "kind", "sha256", "size_bytes", "rows"})
        ref = relative_reference(item["relative_path"])
        if ref in seen:
            raise ValueError("DUPLICATE_FILE_REFERENCE")
        seen.add(ref)
        if not isinstance(item["kind"], str) or item["kind"] not in KINDS:
            raise ValueError("INVALID_FILE_KIND")
        _digest(item["sha256"])
        _count(item["size_bytes"])
        _count(item["rows"])
    quality = _mapping(value["quality"], {"issue_codes"})["issue_codes"]
    if (
        not isinstance(quality, list)
        or any(
            not isinstance(code, str) or not CODE.fullmatch(code) for code in quality
        )
        or quality != sorted(set(quality))
    ):
        raise ValueError("INVALID_QUALITY_CODES")
    _digest(value["fingerprint"])
    if receipt_fingerprint(value) != value["fingerprint"]:
        raise ValueError("FINGERPRINT_MISMATCH")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_receipt_files(receipt: dict, dataset_root: Path) -> list[str]:
    value = validate_input_receipt(receipt)
    issues = set()
    try:
        root = dataset_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ["DATASET_ROOT_UNAVAILABLE"]
    if not root.is_dir():
        return ["DATASET_ROOT_UNAVAILABLE"]
    seen: set[Path] = set()
    for item in value["files"]:
        try:
            file = (root / item["relative_path"]).resolve(strict=True)
            if not file.is_relative_to(root) or not file.is_file() or file in seen:
                issues.add("UNSAFE_FILE_REFERENCE")
                continue
            seen.add(file)
            if (
                file.stat().st_size != item["size_bytes"]
                or sha256_file(file) != item["sha256"]
            ):
                issues.add("FILE_CHANGED")
        except (OSError, RuntimeError):
            issues.add("FILE_UNAVAILABLE")
    return sorted(issues)


def input_issues(receipt: dict) -> list[str]:
    value = validate_input_receipt(receipt)
    issues = set(value["quality"]["issue_codes"])
    if value["availability_state"] != "verified":
        issues.add("UNVERIFIED_AVAILABILITY")
    if value["timezone"] == "unknown":
        issues.add("UNKNOWN_TIMEZONE")
    if value["price_basis"] == "unknown":
        issues.add("UNKNOWN_PRICE_BASIS")
    if value["synthetic"]:
        issues.add("SYNTHETIC_INPUT")
    else:
        # A claimed owner publication is never an independently verified receipt.
        issues.add("OWNER_PROVENANCE_UNVERIFIED")
    return sorted(issues)


def read_json(path: Path) -> object:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("NONFINITE_JSON")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique,
        parse_constant=invalid,
    )


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(
            2,
            json.dumps({"status": "blocked", "issue_codes": ["INVALID_ARGUMENTS"]})
            + "\n",
        )


def main() -> int:
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = validate_input_receipt(read_json(args.receipt))
        problems = check_receipt_files(receipt, args.dataset_root)
        problems = sorted(set(problems) | set(receipt["quality"]["issue_codes"]))
        print(
            json.dumps(
                {
                    "status": "blocked" if problems else "diagnostic_only",
                    "issue_codes": sorted(set(problems) | set(input_issues(receipt))),
                    "fingerprint": receipt["fingerprint"],
                }
            )
        )
        return 2 if problems else 0
    except (OSError, ValueError, TypeError, UnicodeError):
        print(
            json.dumps({"status": "blocked", "issue_codes": ["INVALID_INPUT_RECEIPT"]})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
