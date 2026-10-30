"""Independent file-contract checks for bounded offline experiments."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from ._project_storage import relocated_path, guarded_location


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def lock_digest():
    path = Path(__file__).resolve().parents[2] / "uv.lock"
    if not path.is_file():
        raise ValueError("Reserved research requires a source checkout with uv.lock")
    return digest(path)


def source_digest():
    root = Path(__file__).parent
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        hasher.update(path.relative_to(root).as_posix().encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def claim_reservation(receipt, source, output, protocol, *, claim=True):
    receipt, source, output = (
        relocated_path(receipt).resolve(strict=True),
        relocated_path(source).resolve(strict=True),
        relocated_path(output),
    )
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if set(data) != {"schema", "status", "identity", "owner_root", "output"}:
        raise ValueError("Invalid reservation fields")
    identity = data["identity"]
    key = {k: identity[k] for k in ("protocol", "input_sha256")}
    name = (
        hashlib.sha256(
            json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        + ".json"
    )
    owner = relocated_path(data["owner_root"])
    if (
        data["schema"] != "competition.research_reservation.v1"
        or data["status"] != "reserved"
        or identity["protocol"] != protocol
        or identity["input_sha256"] != digest(source)
        or identity["code_sha256"] != source_digest()
        or identity.get("lock_sha256") != lock_digest()
        or receipt.parent != owner / "research-reservations"
        or receipt.name != name
        or relocated_path(data["output"]) != output
        or output.exists()
        or output == owner
        or not output.is_relative_to(owner)
        or output.is_relative_to(source.parent)
        or any(
            (p / ".git").exists() or (p / "pyproject.toml").exists()
            for p in (output, *output.parents)
        )
        or Path(str(receipt) + ".started").exists()
    ):
        raise ValueError("Input, code, output or reservation state mismatch")
    if claim:
        relative = "research-reservations/" + receipt.name + ".started"
        with guarded_location(owner, relative):
            with Path(str(receipt) + ".started").open("x", encoding="utf-8") as stream:
                stream.write(json.dumps({"status": "started", "pid": os.getpid()}))
    return data


def supervise(module, protocol, seconds, argv=None):
    parser = argparse.ArgumentParser(
        description="Reserved bounded offline research; no broker"
    )
    for name in ("input", "output", "reservation"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    claim_reservation(
        args.reservation, args.input, args.output, protocol, claim=args.worker
    )
    if args.worker:
        return args, None
    env = {
        **os.environ,
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    }
    command = [
        sys.executable,
        "-m",
        module,
        "--input",
        str(args.input.resolve()),
        "--output",
        str(args.output.resolve()),
        "--reservation",
        str(args.reservation.resolve()),
        "--worker",
    ]
    try:
        return args, subprocess.run(command, env=env, timeout=seconds).returncode
    except subprocess.TimeoutExpired:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "timeout.json").write_text(
            json.dumps({"status": "timeout", "seconds": seconds})
        )
        return args, 2
