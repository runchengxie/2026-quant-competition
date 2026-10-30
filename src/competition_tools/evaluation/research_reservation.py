"""Exclusive owner-scoped reservations, independent of result directories."""

import hashlib
import json
from pathlib import Path

from ..project_storage import guarded_location, relocated_path


def _key(identity):
    # Code corrections must not silently mint a second real-data budget.
    key = {k: identity[k] for k in ("protocol", "input_sha256") if k in identity}
    if not key.get("protocol"):
        raise ValueError("Missing protocol identity")
    return hashlib.sha256(
        json.dumps(key, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _check_output(owner, output):
    if output == owner or not output.is_relative_to(owner):
        raise ValueError("Output must be below owner data root")
    if output.exists() or any((p / ".git").exists() for p in (output, *output.parents)):
        raise ValueError("Existing or checkout output is forbidden")


def reserve_run(owner_root, identity, output):
    owner, output = relocated_path(owner_root), relocated_path(output)
    _check_output(owner, output)
    folder = owner / "research-reservations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (_key(identity) + ".json")
    receipt = {
        "schema": "competition.research_reservation.v1",
        "status": "reserved",
        "owner_root": str(owner),
        "output": str(output),
        "identity": identity,
    }
    with guarded_location(owner, "research-reservations/" + path.name):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2, allow_nan=False))
    return path


def validate_reservation(path, identity, output):
    path = relocated_path(path).resolve(strict=True)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (
        set(receipt) != {"schema", "status", "owner_root", "output", "identity"}
        or receipt["schema"] != "competition.research_reservation.v1"
        or receipt["status"] != "reserved"
        or receipt["identity"] != identity
        or path.name != _key(identity) + ".json"
        or relocated_path(receipt["output"]) != relocated_path(output)
        or Path(str(path) + ".started").exists()
    ):
        raise ValueError("Invalid or already started reservation")
    owner = relocated_path(receipt["owner_root"])
    if path.parent != owner / "research-reservations":
        raise ValueError("Reservation outside authoritative owner")
    _check_output(owner, relocated_path(output))
    return receipt
