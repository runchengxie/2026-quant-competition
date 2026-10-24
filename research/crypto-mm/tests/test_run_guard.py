import hashlib
import json

import pytest


def test_guard_claims_once_and_rejects_changed_input(tmp_path):
    from crypto_mm.run_guard import claim_reservation, source_digest

    source = tmp_path / "inputs" / "input.json"
    source.parent.mkdir()
    source.write_text("original")
    identity = {
        "protocol": "synthetic.v1",
        "input_sha256": hashlib.sha256(b"original").hexdigest(),
        "code_sha256": source_digest(),
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
