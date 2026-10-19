"""Daily inputs must remain exact bytes and never become vendor attestation."""

import hashlib
import json
import os
import subprocess
import sys

import pandas as pd
import pytest

from equity_lab.validation import validate_inputs


def input_manifest(tmp_path, frame=None):
    frame = (
        frame
        if frame is not None
        else pd.DataFrame(
            {
                "date": ["2026-01-02"],
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [100.0],
                "code": ["HK.TEST"],
            }
        )
    )
    path = tmp_path / "bars.csv"
    frame.to_csv(path, index=False)
    content = path.read_bytes()
    value = {
        "schema_version": "competition.research_input_manifest.v1",
        "dataset_root": str(tmp_path),
        "producer": {
            "package": "competition-equity-lab",
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
                "relative_path": path.name,
                "kind": "daily_bars",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        ],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(value))
    return manifest, value


def test_receipt_contains_only_relative_refs_and_preserves_inputs(tmp_path):
    path, _ = input_manifest(tmp_path)
    before = (tmp_path / "bars.csv").read_bytes()
    value = validate_inputs(path)
    assert value["schema_version"] == "competition.research_input_receipt.v1"
    assert value["files"][0]["rows"] == 1
    assert value["quality"] == {"issue_codes": []}
    assert "dataset_root" not in value
    assert (tmp_path / "bars.csv").read_bytes() == before


@pytest.mark.parametrize(
    "column,value",
    [
        ("open", float("inf")),
        ("close", 0),
        ("high", 1),
        ("low", 20),
        ("volume", -1),
        ("volume", float("nan")),
        ("code", "US.TEST"),
        ("date", "not-a-date"),
        ("date", "2026-01-02T00:00:00+00:00"),
        ("date", "2026-01-02T12:00:00"),
    ],
)
def test_rejects_invalid_daily_values(tmp_path, column, value):
    frame = pd.DataFrame(
        {
            "date": ["2026-01-02"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [100.0],
            "code": ["HK.TEST"],
        }
    )
    frame[column] = value
    path, _ = input_manifest(tmp_path, frame)
    with pytest.raises(ValueError):
        validate_inputs(path)


def test_duplicate_date_code_rejected_across_files(tmp_path):
    path, value = input_manifest(tmp_path)
    (tmp_path / "other.csv").write_bytes((tmp_path / "bars.csv").read_bytes())
    value["files"].append(value["files"][0] | {"relative_path": "other.csv"})
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="DUPLICATE"):
        validate_inputs(path)


@pytest.mark.parametrize(
    "change",
    [
        {"market": "CRYPTO"},
        {"timezone": "Mars/Unknown"},
        {"synthetic": 1},
        {"extra": "unreviewed"},
        {"dataset_root": "relative"},
    ],
)
def test_invalid_manifest_metadata_rejected(tmp_path, change):
    path, value = input_manifest(tmp_path)
    path.write_text(json.dumps(value | change))
    with pytest.raises(ValueError):
        validate_inputs(path)


def test_changed_input_and_path_escape_rejected(tmp_path):
    path, value = input_manifest(tmp_path)
    (tmp_path / "bars.csv").write_text("changed bytes")
    with pytest.raises(ValueError, match="FILE_CHANGED"):
        validate_inputs(path)
    value["files"][0]["relative_path"] = "../outside.csv"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="UNSAFE"):
        validate_inputs(path)


def test_cli_help_no_data_config_and_exclusive_output(tmp_path):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATA_ROOT", "WORKSPACE_CONFIG", "CONFIG_ROOT"}
    }
    env["WORKSPACE_CONFIG"] = str(tmp_path / "missing.toml")
    command = [sys.executable, "-m", "equity_lab.validation"]
    assert (
        subprocess.run(command + ["--help"], env=env, capture_output=True).returncode
        == 0
    )
    path, _ = input_manifest(tmp_path)
    output = tmp_path / "receipt.json"
    first = subprocess.run(
        command + ["--manifest", str(path), "--output", str(output)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    before = output.read_bytes()
    second = subprocess.run(
        command + ["--manifest", str(path), "--output", str(output)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 2
    assert str(tmp_path) not in second.stdout + second.stderr
    assert output.read_bytes() == before


@pytest.mark.parametrize("values", [[True], [True, "invalid"]])
def test_boolean_ohlcv_never_certified_as_prices(tmp_path, values):
    frame = pd.DataFrame(
        {name: values for name in ("open", "high", "low", "close", "volume")}
    )
    frame["date"] = "2026-01-02"
    frame["code"] = "HK.TEST"
    path, _ = input_manifest(tmp_path, frame)
    with pytest.raises(ValueError, match="INVALID_NUMERIC_DATA"):
        validate_inputs(path)


def test_parser_error_does_not_echo_private_arguments():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "equity_lab.validation",
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
