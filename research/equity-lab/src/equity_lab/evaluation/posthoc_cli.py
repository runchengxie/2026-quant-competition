"""Supplied-file-only producer; root independently verifies all saved calculations."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from .posthoc_report import evaluate


def hashed(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("DUPLICATE_POSTHOC_FIELD")
            result[k] = v
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("NONFINITE_POSTHOC_JSON")
        ),
    )


def produce(protocol):
    path = Path(protocol)
    b = load(path)
    if (
        b.get("schema") != "competition.posthoc_diagnostics_protocol.v1"
        or hashed({k: v for k, v in b.items() if k != "binding_sha256"})
        != b["binding_sha256"]
    ):
        raise ValueError("INVALID_POSTHOC_PROTOCOL")
    owner, output = Path(b["owner"]), Path(b["output"])
    if path.resolve() != (owner / "protocol.json").resolve() or not output.is_dir():
        raise ValueError("INVALID_POSTHOC_LOCATION")
    if load(output / "started.json") != dict(binding_sha256=b["binding_sha256"]):
        raise ValueError("POSTHOC_START_BINDING_CHANGED")
    expected_source = (
        Path(b["source"]["identity"]["source_root"])
        / "research/equity-lab/src/equity_lab/evaluation/posthoc_cli.py"
    )
    if Path(__file__).resolve() != expected_source.resolve():
        raise ValueError("POSTHOC_EXECUTING_SOURCE_CHANGED")
    with (output / "producer-started.json").open("x", encoding="utf-8") as stream:
        json.dump(dict(binding_sha256=b["binding_sha256"]), stream)
        stream.flush()
        os.fsync(stream.fileno())
    evidence = load(owner / "inputs.json")
    if hashed(evidence) != b["evidence_sha256"]:
        raise ValueError("POSTHOC_INPUT_HASH_CHANGED")
    result = dict(binding_sha256=b["binding_sha256"], **evaluate(evidence, b["family"]))
    with (output / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args(argv)
    produce(args.protocol)


if __name__ == "__main__":
    main()
