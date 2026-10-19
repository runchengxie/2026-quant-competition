"""Exact-byte input receipts are diagnostic evidence, not vendor attestation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from competition_tools.research_acceptance import (
    check_receipt_files,
    input_issues,
    receipt_fingerprint,
    validate_input_receipt,
)


def receipt(root: Path) -> dict:
    content = b"date,close\n2026-01-01,10\n"
    (root / "bars.csv").write_bytes(content)
    value = {
        "schema_version": "competition.research_input_receipt.v1",
        "producer": {
            "package": "test-producer",
            "package_version": "0.1.0",
            "code_revision": "unknown",
        },
        "dataset_id": "fixture-v1",
        "market": "HK",
        "synthetic": True,
        "source_state": "synthetic",
        "timezone": "Asia/Hong_Kong",
        "price_basis": "raw",
        "universe_state": "synthetic",
        "availability_state": "unknown",
        "files": [
            {
                "relative_path": "bars.csv",
                "kind": "daily_bars",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "rows": 1,
            }
        ],
        "quality": {"issue_codes": []},
    }
    value["fingerprint"] = receipt_fingerprint(value)
    return value


def test_valid_receipt_and_published_schema(tmp_path):
    value = receipt(tmp_path)
    assert validate_input_receipt(value) == value
    assert check_receipt_files(value, tmp_path) == []
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/input-receipt.v1.schema.json"
        ).read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(value)


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "v999"},
        {"unknown": True},
        {"synthetic": 1},
        {"market": "CN"},
        {"timezone": "Mars/Unknown"},
        {"source_state": "owner_published"},
    ],
)
def test_unknown_schema_and_invalid_metadata_rejected(tmp_path, change):
    value = receipt(tmp_path) | change
    value["fingerprint"] = receipt_fingerprint(value)
    with pytest.raises(ValueError):
        validate_input_receipt(value)


@pytest.mark.parametrize(
    "field,value",
    [("rows", True), ("rows", float("nan")), ("size_bytes", -1), ("sha256", "A" * 64)],
)
def test_nonfinite_and_boolean_counts_rejected(tmp_path, field, value):
    payload = receipt(tmp_path)
    payload["files"][0][field] = value
    with pytest.raises(ValueError):
        payload["fingerprint"] = receipt_fingerprint(payload)
        validate_input_receipt(payload)


def test_changed_bytes_and_newline_conversion_rejected(tmp_path):
    value = receipt(tmp_path)
    file = tmp_path / "bars.csv"
    file.write_bytes(file.read_bytes().replace(b"\n", b"\r\n"))
    assert check_receipt_files(value, tmp_path) == ["FILE_CHANGED"]


@pytest.mark.parametrize(
    "path",
    ["../outside.csv", "/bars.csv", "C:/bars.csv", "a\\bars.csv", "./bars.csv", "."],
)
def test_escaping_refs_rejected(tmp_path, path):
    value = receipt(tmp_path)
    value["files"][0]["relative_path"] = path
    value["fingerprint"] = receipt_fingerprint(value)
    with pytest.raises(ValueError):
        validate_input_receipt(value)


def test_duplicate_refs_rejected(tmp_path):
    value = receipt(tmp_path)
    value["files"].append(deepcopy(value["files"][0]))
    value["fingerprint"] = receipt_fingerprint(value)
    with pytest.raises(ValueError):
        validate_input_receipt(value)


def test_symlink_escape_rejected_before_hashing(tmp_path):
    value = receipt(tmp_path)
    outside = tmp_path.parent / "outside-bars.csv"
    outside.write_text("private input")
    file = tmp_path / "bars.csv"
    file.unlink()
    try:
        file.symlink_to(outside)
    except OSError:
        pytest.skip("Platform does not permit symlinks")
    assert check_receipt_files(value, tmp_path) == ["UNSAFE_FILE_REFERENCE"]


def test_unknown_metadata_is_diagnostic_only(tmp_path):
    value = receipt(tmp_path)
    assert "UNVERIFIED_AVAILABILITY" in input_issues(value)
    value.update(
        synthetic=False,
        source_state="owner_published",
        universe_state="point_in_time",
        availability_state="verified",
    )
    value["fingerprint"] = receipt_fingerprint(value)
    assert "OWNER_PROVENANCE_UNVERIFIED" in input_issues(value)


def test_symlink_loop_has_safe_diagnostic(tmp_path):
    value = receipt(tmp_path)
    path = tmp_path / "bars.csv"
    path.unlink()
    try:
        path.symlink_to(path)
    except OSError:
        pytest.skip("Platform does not permit symlinks")
    assert check_receipt_files(value, tmp_path) == ["FILE_UNAVAILABLE"]


def test_fingerprint_binds_metadata_and_exact_bytes(tmp_path):
    value = receipt(tmp_path)
    value["price_basis"] = "adjusted"
    with pytest.raises(ValueError, match="FINGERPRINT"):
        validate_input_receipt(value)


def test_cli_help_and_safe_error_without_private_path(tmp_path):
    help_run = subprocess.run(
        [sys.executable, "-m", "competition_tools.research_acceptance", "--help"],
        capture_output=True,
        text=True,
    )
    assert help_run.returncode == 0
    bad = subprocess.run(
        [
            sys.executable,
            "-m",
            "competition_tools.research_acceptance",
            "--receipt",
            str(tmp_path / "private-secret.json"),
            "--dataset-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 2
    assert "private-secret" not in bad.stdout + bad.stderr
