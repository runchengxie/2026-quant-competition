"""Owner-scoped immutable starts for the supported reserved forest study APIs.

These guards prevent accidental budget resets, not arbitrary owner Python or
scikit-learn execution. Explicit synthetic fitter injection is a test seam.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets

from equity_lab._project_storage import guarded_location, relocated_path
from equity_lab.run_guard import source_digest, lock_digest

PROTOCOL = "equity.low_turnover_forest.20261031.v1"


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _read(path):
    return json.loads(relocated_path(path).read_text(encoding="utf-8"))


def _write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, allow_nan=False))
        stream.flush()
        os.fsync(stream.fileno())


def receipt_for(reservation, binding):
    path = relocated_path(reservation)
    receipt = _read(path)
    if set(receipt) != {"schema", "status", "identity", "owner_root", "output"}:
        raise ValueError("INVALID_FOREST_RESERVATION")
    identity = receipt["identity"]
    owner = relocated_path(receipt["owner_root"])
    output = relocated_path(receipt["output"])
    key = dict(protocol=identity["protocol"], input_sha256=identity["input_sha256"])
    if (
        receipt["schema"] != "competition.research_reservation.v1"
        or receipt["status"] != "reserved"
        or path.parent != owner / "research-reservations"
        or path.name != _hash(key) + ".json"
        or key["protocol"] != PROTOCOL
        or key["input_sha256"] != binding["input_sha256"]
        or identity["binding_sha256"] != binding["binding_sha256"]
        or identity["code_sha256"] != source_digest()
        or identity["lock_sha256"] != lock_digest()
        or output != relocated_path(binding["output"])
        or owner != relocated_path(binding["owner"])
        or output == owner
        or not output.is_relative_to(owner)
        or not Path(str(path) + ".started").is_file()
    ):
        raise ValueError("INVALID_FOREST_RESERVATION_START_BINDING")
    return path, receipt


def start_forest(reservation, binding):
    path, receipt = receipt_for(reservation, binding)
    if relocated_path(binding["output"]).exists():
        raise ValueError("FOREST_OUTPUT_ALREADY_EXISTS")
    token = secrets.token_hex(32)
    owner = relocated_path(receipt["owner_root"])
    relative = "research-reservations/" + path.name + ".forest-started"
    with guarded_location(owner, relative):
        _write(
            owner / relative,
            dict(
                schema="equity.forest_start.v1",
                receipt=receipt,
                token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                pid=os.getpid(),
            ),
        )
    return token


def validate_start(reservation, binding, *, token=True):
    path, receipt = receipt_for(reservation, binding)
    snapshot = _read(Path(str(path) + ".forest-started"))
    if (
        set(snapshot) != {"schema", "receipt", "token_sha256", "pid"}
        or snapshot["schema"] != "equity.forest_start.v1"
        or snapshot["receipt"] != receipt
        or type(snapshot["pid"]) is not int
        or snapshot["pid"] <= 0
    ):
        raise ValueError("FOREST_INITIAL_START_CHANGED")
    current = os.environ.get("GMR_FOREST_WORKER_TOKEN", "")
    if token and (
        not current
        or hashlib.sha256(current.encode()).hexdigest() != snapshot["token_sha256"]
    ):
        raise ValueError("FOREST_WORKER_TOKEN_REQUIRED")
    return path, receipt


def claim_horizon(reservation, binding, horizon):
    if type(horizon) is not int or horizon not in (5, 20):
        raise ValueError("INVALID_FOREST_HORIZON_CLAIM")
    path, receipt = validate_start(reservation, binding)
    owner = relocated_path(receipt["owner_root"])
    relative = "research-reservations/" + path.name + f".h{horizon}.started"
    with guarded_location(owner, relative):
        _write(
            owner / relative,
            dict(
                schema="equity.forest_horizon_start.v1",
                horizon=horizon,
                pid=os.getpid(),
                binding_sha256=binding["binding_sha256"],
                output=str(relocated_path(binding["output"]) / f"h{horizon}"),
            ),
        )
    return dict(
        reservation=str(path), horizon=horizon, claim_path=str(owner / relative)
    )


def validate_claim(claim, binding, output, horizons):
    if (
        not isinstance(claim, dict)
        or set(claim) != {"reservation", "horizon", "claim_path"}
        or tuple(horizons) != (claim["horizon"],)
    ):
        raise ValueError("FOREST_HORIZON_CLAIM_REQUIRED")
    path, receipt = validate_start(claim["reservation"], binding)
    h = claim["horizon"]
    marker = Path(str(path) + f".h{h}.started")
    if relocated_path(claim["claim_path"]) != marker:
        raise ValueError("FOREST_HORIZON_CLAIM_CHANGED")
    saved = _read(marker)
    if (
        set(saved) != {"schema", "horizon", "pid", "binding_sha256", "output"}
        or saved["schema"] != "equity.forest_horizon_start.v1"
        or saved["pid"] != os.getpid()
        or saved["horizon"] != h
        or saved["binding_sha256"] != binding["binding_sha256"]
        or relocated_path(saved["output"]) != relocated_path(output)
        or relocated_path(output) != relocated_path(binding["output"]) / f"h{h}"
    ):
        raise ValueError("FOREST_HORIZON_CLAIM_CHANGED")
    return Path(str(path) + f".h{h}.attempts.jsonl")
