"""The explicit manifest, not eager project config, owns inspection inputs."""

import hashlib
import json
import os
import subprocess
import sys

import polars as pl
import pytest

from crypto_mm.demo import build_demo_data
from crypto_mm.research.input_validation import validate_inputs


def input_manifest(tmp_path):
    raw = tmp_path / "raw"
    paths = build_demo_data(raw)
    files = [
        {
            "relative_path": path.relative_to(raw).as_posix(),
            "kind": path.parent.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
    ]
    value = {
        "schema_version": "competition.research_input_manifest.v1",
        "dataset_root": str(raw),
        "producer": {
            "package": "competition-crypto-mm",
            "package_version": "0.1.0",
            "code_revision": "unknown",
        },
        "dataset_id": "fixture-events-v1",
        "market": "CRYPTO",
        "synthetic": True,
        "source_state": "synthetic",
        "timezone": "unknown",
        "price_basis": "raw",
        "universe_state": "synthetic",
        "availability_state": "unknown",
        "files": files,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    return path, value, raw


def test_receipt_reuses_audit_and_preserves_unknown_provenance(tmp_path):
    path, manifest, raw = input_manifest(tmp_path)
    value = validate_inputs(path)
    assert len(value["files"]) == 9
    assert value["quality"] == {"issue_codes": []}
    assert value["timezone"] == "unknown"
    assert "dataset_root" not in value
    assert [(f["sha256"], f["size_bytes"]) for f in value["files"]] == [
        (f["sha256"], f["size_bytes"]) for f in manifest["files"]
    ]
    for item in value["files"]:
        assert (
            hashlib.sha256((raw / item["relative_path"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def test_missing_group_rejected(tmp_path):
    path, value, _ = input_manifest(tmp_path)
    value["files"] = [f for f in value["files"] if f["kind"] != "trades"]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="MISSING_DATASET_GROUP"):
        validate_inputs(path)


@pytest.mark.parametrize("bad", [float("nan"), -1.0])
def test_nonfinite_or_negative_trade_rejected(tmp_path, bad):
    path, value, raw = input_manifest(tmp_path)
    item = next(f for f in value["files"] if f["kind"] == "trades")
    file = raw / item["relative_path"]
    pl.read_parquet(file).with_columns(pl.lit(bad).alias("price")).write_parquet(file)
    item.update(
        sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
        size_bytes=file.stat().st_size,
    )
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        validate_inputs(path)


def test_changed_bytes_and_metadata_rejected(tmp_path):
    path, value, raw = input_manifest(tmp_path)
    (raw / value["files"][0]["relative_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="FILE_CHANGED"):
        validate_inputs(path)
    path.write_text(json.dumps(value | {"synthetic": "false"}))
    with pytest.raises(ValueError):
        validate_inputs(path)


def test_explicit_manifest_works_without_global_data_config(tmp_path):
    path, _, _ = input_manifest(tmp_path)
    env = dict(os.environ)
    env.pop("DATA_ROOT", None)
    env["WORKSPACE_CONFIG"] = str(tmp_path / "missing-private.toml")
    command = [sys.executable, "-m", "crypto_mm.commands.validate_inputs"]
    assert (
        subprocess.run(command + ["--help"], env=env, capture_output=True).returncode
        == 0
    )
    output = tmp_path / "receipt.json"
    result = subprocess.run(
        command + ["--manifest", str(path), "--output", str(output)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["timezone"] == "unknown"
    again = subprocess.run(
        command + ["--manifest", str(path), "--output", str(output)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert again.returncode == 2
    assert str(tmp_path) not in again.stdout + again.stderr


@pytest.mark.parametrize("unit,zone", [("us", None), ("ns", "UTC")])
def test_timestamp_precision_and_zone_are_not_relabelled(tmp_path, unit, zone):
    path, value, raw = input_manifest(tmp_path)
    item = value["files"][0]
    file = raw / item["relative_path"]
    pl.read_parquet(file).with_columns(
        pl.col("datetime").dt.replace_time_zone(zone).cast(pl.Datetime(unit, zone))
    ).write_parquet(file)
    item.update(
        sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
        size_bytes=file.stat().st_size,
    )
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="TIMESTAMP_PRECISION|TIMEZONE_MISMATCH"):
        validate_inputs(path)


def test_missing_daily_group_rejected(tmp_path):
    path, value, _ = input_manifest(tmp_path)
    value["files"].remove(next(f for f in value["files"] if f["kind"] == "trades"))
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="MISSING_DATASET_GROUP"):
        validate_inputs(path)


def test_parser_error_does_not_echo_private_arguments():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.commands.validate_inputs",
            "--manifest",
            "dummy.json",
            "--output",
            "dummy.json",
            "D:/private/account-123/data.csv",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "D:/private" not in result.stdout + result.stderr
    assert "INVALID_ARGUMENTS" in result.stdout + result.stderr
