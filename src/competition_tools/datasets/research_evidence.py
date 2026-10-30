"""Verify retained daily bytes and inventory unverified research requirements."""

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re

from .daily_spec import validate_daily_spec
from .daily_storage import safe_path, verify_daily_manifest
from .storage import digest


BLOCKERS = (
    "POINT_IN_TIME_UNIVERSE_UNVERIFIED",
    "HISTORICAL_SECURITY_IDENTITY_UNVERIFIED",
    "CORPORATE_ACTION_COVERAGE_UNVERIFIED",
    "HISTORICAL_AVAILABILITY_UNVERIFIED",
    "OWNER_PROVENANCE_UNVERIFIED",
    "HOLDOUT_GOVERNANCE_UNVERIFIED",
)
MANIFEST_KEYS = set(
    "schema dataset_id version spec_hash spec receipt observed_at status coverage gaps "
    "files parent_manifest_sha256 accepted_research".split()
)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("NONFINITE_JSON")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("NONFINITE_JSON")
    return number


def _read(path):
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=_nonfinite,
        parse_float=_float,
    )
    if not isinstance(value, dict):
        raise ValueError("INVALID_EVIDENCE_OBJECT")
    return value


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _validate_metadata(value):
    try:
        timestamp = value["observed_at"]
        if (
            not isinstance(timestamp, str)
            or datetime.fromisoformat(timestamp).utcoffset() is None
        ):
            raise ValueError
        if (
            not _hash(value["spec_hash"])
            or value["status"] not in ("acquired", "partial")
            or not isinstance(value["coverage"], dict)
            or not isinstance(value["gaps"], list)
            or (
                value["parent_manifest_sha256"] is not None
                and not _hash(value["parent_manifest_sha256"])
            )
            or value["accepted_research"] is not False
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("INVALID_DAILY_EVIDENCE_METADATA") from None


def _validate_manifest(value, path):
    if (
        set(value) != MANIFEST_KEYS
        or value["schema"] != "competition.dataset_manifest.v2"
        or value["accepted_research"] is not False
        or not isinstance(value["spec"], dict)
        or "connection_file" in value["spec"]
    ):
        raise ValueError("INVALID_DAILY_EVIDENCE_MANIFEST")
    _validate_metadata(value)
    receipt = value["receipt"]
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "competition.dataset_receipt.v2"
    ):
        raise ValueError("INVALID_DAILY_EVIDENCE_RECEIPT")
    _validate_metadata(receipt)
    if any(
        value[key] != receipt[key]
        for key in (
            "spec_hash",
            "observed_at",
            "status",
            "coverage",
            "gaps",
            "parent_manifest_sha256",
        )
    ):
        raise ValueError("RECEIPT_METADATA_MISMATCH")
    # The producer deliberately omits this private path from published metadata.
    # Use a placeholder for structural validation only; never read it or rehash it.
    validate_daily_spec(
        value["spec"] | {"connection_file": str(path.parent / "unused-connection.json")}
    )
    if any(value[key] != value["spec"][key] for key in ("dataset_id", "version")):
        raise ValueError("DATASET_IDENTITY_MISMATCH")
    if (
        not isinstance(value["files"], list)
        or not value["files"]
        or any(
            not isinstance(item, dict)
            or set(item) != {"path", "sha256", "bytes"}
            or not isinstance(item["sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", item["sha256"]) is None
            or type(item["bytes"]) is not int
            or item["bytes"] < 0
            for item in value["files"]
        )
    ):
        raise ValueError("INVALID_MANIFEST_FILES")


def audit_daily_research_evidence(manifest_path: Path, expected_sha256: str) -> dict:
    """Return blocked-only inventory after verifying the selected v2 producer."""
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None
    ):
        raise ValueError("INVALID_EXPECTED_MANIFEST_HASH")
    path = safe_path(Path(manifest_path))
    receipt_path = safe_path(path.parent / "receipt.json")
    before = digest(path)
    receipt_before = digest(receipt_path)
    if before != expected_sha256:
        raise ValueError("MANIFEST_HASH_MISMATCH")
    value = _read(path)
    receipt = _read(receipt_path)
    _validate_manifest(value, path)
    if value["receipt"] != receipt:
        raise ValueError("RECEIPT_MISMATCH")
    verified = verify_daily_manifest(path)
    if (
        digest(path) != before
        or digest(receipt_path) != receipt_before
        or verified != value
    ):
        raise ValueError("EVIDENCE_CHANGED_DURING_VERIFICATION")
    return dict(
        schema="competition.daily_research_evidence_gap.v1",
        dataset_id=value["dataset_id"],
        version=value["version"],
        market=value["spec"]["market"],
        manifest_sha256=before,
        receipt_sha256=receipt_before,
        payload_files=len(value["files"]),
        payload_bytes=sum(item["bytes"] for item in value["files"]),
        checks=[dict(code="RETAINED_BYTES_VERIFIED", status="passed")]
        + [dict(code=code, status="blocked") for code in BLOCKERS],
        status="blocked",
        accepted_research=False,
        execution_authorized=False,
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INVALID_ARGUMENTS")


def _publish(output, value):
    # Exclusive creation protects a concurrent winner without replacing it.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        owned = os.fstat(stream.fileno())
        try:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            if output.exists() and os.path.samestat(owned, output.stat()):
                output.unlink()
            raise


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True)
    try:
        args = parser.parse_args(argv)
        path = safe_path(Path(args.manifest))
        output = safe_path(Path(args.output))
        if output.is_relative_to(path.parent):
            raise ValueError("OUTPUT_INSIDE_INPUT_DATASET")
        if output.exists():
            raise ValueError("EVIDENCE_OUTPUT_EXISTS")
        if not output.parent.is_dir():
            raise ValueError("OUTPUT_PARENT_REQUIRED")
        value = audit_daily_research_evidence(path, args.expected_sha256)
        _publish(output, value)
        print(json.dumps({"status": "blocked", "report_written": True}))
        return 0
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
    ) as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", code):
            code = "EVIDENCE_AUDIT_FAILED"
        print(json.dumps({"status": "error", "code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
