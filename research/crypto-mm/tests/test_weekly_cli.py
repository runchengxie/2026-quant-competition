from datetime import date, timedelta
import hashlib
import json
import subprocess
import sys

import pytest


def batch():
    windows = []
    for index in range(12):
        first = date(2020, 1, 1) + timedelta(days=90 * index)
        dates = [(first + timedelta(days=day)).isoformat() for day in range(342)]
        windows.append(
            {
                "window_id": dates[252],
                "parent_sha256": "a" * 64,
                "bars": {
                    "dates": dates,
                    "close": {f"P{i}": [100] * 342 for i in range(8)},
                },
            }
        )
    return {"schema": "crypto.weekly_input.v1", "windows": windows}


@pytest.mark.parametrize(
    "identifier", ["../escaped", "..\\escaped", "C:\\escaped", "/escaped", "2021-01-01"]
)
def test_weekly_batch_rejects_path_or_wrong_start_identifiers(identifier):
    from crypto_mm.daily.weekly_cli import validate_batch

    value = batch()
    value["windows"][0]["window_id"] = identifier
    with pytest.raises(ValueError):
        validate_batch(value)


def test_weekly_batch_and_artifact_stay_in_reserved_directory(tmp_path):
    from crypto_mm.daily.weekly_cli import validate_batch, artifact_path

    value = batch()
    assert validate_batch(value) == value
    path = artifact_path(tmp_path, "2026-08-03", 35, "weekly_trend")
    assert path.parent == tmp_path.resolve()
    with pytest.raises(ValueError):
        artifact_path(tmp_path, "../escaped", 35, "weekly_trend")


def test_actual_cli_rejects_traversal_before_writing_results(tmp_path):
    from crypto_mm.run_guard import lock_digest, source_digest
    from crypto_mm.daily.weekly_cli import PROTOCOL

    source = tmp_path / "inputs" / "batch.json"
    source.parent.mkdir()
    value = batch()
    value["windows"][0]["window_id"] = "../escaped"
    source.write_text(json.dumps(value))
    identity = {
        "protocol": PROTOCOL,
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "code_sha256": source_digest(),
        "lock_sha256": lock_digest(),
    }
    key = {k: identity[k] for k in ("protocol", "input_sha256")}
    name = hashlib.sha256(
        json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    folder = tmp_path / "research-reservations"
    folder.mkdir()
    receipt = folder / (name + ".json")
    output = tmp_path / "out"
    receipt.write_text(
        json.dumps(
            {
                "schema": "competition.research_reservation.v1",
                "status": "reserved",
                "identity": identity,
                "owner_root": str(tmp_path),
                "output": str(output),
            }
        )
    )
    existing = tmp_path / "escaped-35-daily_trend.json"
    existing.write_text("preserve")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.daily.weekly_cli",
            "--input",
            str(source),
            "--output",
            str(output),
            "--reservation",
            str(receipt),
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert not output.exists()
    assert existing.read_text() == "preserve"
