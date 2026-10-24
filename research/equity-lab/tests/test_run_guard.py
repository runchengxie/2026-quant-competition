import hashlib
import json

import pytest


@pytest.mark.parametrize("recorded_lock", [None, "0" * 64])
def test_guard_requires_the_recorded_dependency_lock(tmp_path, recorded_lock):
    from equity_lab.run_guard import claim_reservation, source_digest

    source = tmp_path / "inputs" / "input.json"
    source.parent.mkdir()
    source.write_text("synthetic")
    identity = {
        "protocol": "synthetic.lock.v1",
        "input_sha256": hashlib.sha256(b"synthetic").hexdigest(),
        "code_sha256": source_digest(),
    }
    if recorded_lock is not None:
        identity["lock_sha256"] = recorded_lock
    key = {k: identity[k] for k in ("protocol", "input_sha256")}
    name = hashlib.sha256(
        json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    folder = tmp_path / "research-reservations"
    folder.mkdir()
    receipt = folder / (name + ".json")
    receipt.write_text(
        json.dumps(
            {
                "schema": "competition.research_reservation.v1",
                "status": "reserved",
                "identity": identity,
                "owner_root": str(tmp_path),
                "output": str(tmp_path / "result"),
            }
        )
    )
    with pytest.raises(ValueError):
        claim_reservation(receipt, source, tmp_path / "result", "synthetic.lock.v1")
    assert not (folder / (name + ".json.started")).exists()


def test_supervisor_terminates_a_hung_synthetic_worker(tmp_path, monkeypatch):
    from equity_lab.run_guard import lock_digest, source_digest, supervise

    source = tmp_path / "inputs" / "input.json"
    source.parent.mkdir()
    source.write_text("synthetic")
    identity = {
        "protocol": "synthetic.timeout.v1",
        "input_sha256": hashlib.sha256(b"synthetic").hexdigest(),
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
    output = tmp_path / "result"
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
    sleeper = tmp_path / "synthetic_hung_worker.py"
    marker = tmp_path / "worker-started"
    sleeper.write_text(
        "import time\nfrom pathlib import Path\nPath("
        + repr(str(marker))
        + ").write_text('started')\ntime.sleep(30)\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    _, code = supervise(
        "synthetic_hung_worker",
        "synthetic.timeout.v1",
        1,
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--reservation",
            str(receipt),
        ],
    )
    assert marker.is_file()
    assert code == 2
    assert json.loads((output / "timeout.json").read_text()) == {
        "status": "timeout",
        "seconds": 1,
    }


def test_guard_claims_once_and_rejects_changed_input(tmp_path):
    from equity_lab.run_guard import claim_reservation, lock_digest, source_digest

    source = tmp_path / "inputs" / "input.json"
    source.parent.mkdir()
    source.write_text("original")
    identity = {
        "protocol": "synthetic.v1",
        "input_sha256": hashlib.sha256(b"original").hexdigest(),
        "code_sha256": source_digest(),
        "lock_sha256": lock_digest(),
    }
    key = {k: identity[k] for k in ("protocol", "input_sha256")}
    digest = hashlib.sha256(
        json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    folder = tmp_path / "research-reservations"
    folder.mkdir()
    receipt = folder / (digest + ".json")
    receipt.write_text(
        json.dumps(
            {
                "schema": "competition.research_reservation.v1",
                "status": "reserved",
                "identity": identity,
                "owner_root": str(tmp_path),
                "output": str(tmp_path / "output"),
            }
        )
    )
    source.write_text("changed")
    with pytest.raises(ValueError):
        claim_reservation(receipt, source, tmp_path / "output", "synthetic.v1")
    assert not (folder / (digest + ".json.started")).exists()
    source.write_text("original")
    claim_reservation(receipt, source, tmp_path / "output", "synthetic.v1")
    with pytest.raises((ValueError, FileExistsError)):
        claim_reservation(receipt, source, tmp_path / "another-output", "synthetic.v1")
