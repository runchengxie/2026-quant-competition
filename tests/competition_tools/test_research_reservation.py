from pathlib import Path

import pytest


def test_reserved_identity_cannot_run_again_at_another_output(tmp_path):
    from competition_tools.evaluation.research_reservation import (
        reserve_run,
        validate_reservation,
    )

    owner = tmp_path / "owner"
    identity = {
        "protocol": "test.v1",
        "input_sha256": "a" * 64,
        "code_sha256": "b" * 64,
    }
    receipt = reserve_run(owner, identity, owner / "first")
    assert (
        validate_reservation(receipt, identity, owner / "first")["status"] == "reserved"
    )
    with pytest.raises(FileExistsError):
        reserve_run(owner, identity, owner / "different")
    with pytest.raises(ValueError):
        validate_reservation(
            receipt, identity | {"input_sha256": "c" * 64}, owner / "first"
        )


def test_reservation_rejects_checkout_or_outside_owner_output(tmp_path):
    from competition_tools.evaluation.research_reservation import reserve_run

    owner = tmp_path / "owner"
    with pytest.raises(ValueError):
        reserve_run(owner, {"protocol": "test"}, tmp_path / "escape")
    checkout = owner / "checkout"
    checkout.mkdir(parents=True)
    (checkout / ".git").mkdir()
    with pytest.raises(ValueError):
        reserve_run(owner, {"protocol": "test"}, checkout / "output")


def test_unknown_started_state_blocks_validation(tmp_path):
    from competition_tools.evaluation.research_reservation import (
        reserve_run,
        validate_reservation,
    )

    owner = tmp_path / "owner"
    identity = {"protocol": "test.v1"}
    receipt = reserve_run(owner, identity, owner / "out")
    Path(str(receipt) + ".started").write_text("unknown")
    with pytest.raises(ValueError):
        validate_reservation(receipt, identity, owner / "out")
