"""Dispatch fixed factor protocols to the independently installed research CLI."""

import subprocess
from pathlib import Path

from .config import TeamConfig
from .processes import child_environment, interpreter, run_child, envelope
from competition_tools.datasets.dex_spec import safe_path
from competition_tools.datasets.dex_storage import read_json, verify_dex_manifest
from competition_tools.datasets.storage import digest

from competition_tools.datasets.dex_protocol import (
    SIGNALS as SIGNALS,
    load_factor_protocol,
)


def execute(config: TeamConfig, spec_path: Path, output_root: Path) -> dict:
    spec_path, output = safe_path(spec_path), safe_path(output_root)
    protocol = load_factor_protocol(spec_path)
    manifest = verify_dex_manifest(safe_path(protocol["manifest_file"]))
    if digest(spec_path) != manifest["protocol_sha256"]:
        raise ValueError("FACTOR_PROTOCOL_HASH_MISMATCH")
    environment = child_environment(config)
    for key in list(environment):
        if key.upper() == "DEXPAPRIKA_API_KEY":
            del environment[key]
    command = [
        str(interpreter(config, "crypto-mm")),
        "-m",
        "crypto_mm.factors",
        "--spec",
        str(spec_path),
        "--output-root",
        str(output),
    ]
    try:
        child = run_child(command, environment=environment, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return envelope("factors", issues=["FACTOR_CHILD_UNAVAILABLE"])
    if child.returncode != 0:
        return envelope("factors", issues=["FACTOR_CHILD_FAILED"])
    result = read_json(safe_path(output / "result.json"))
    if (
        result.get("schema") != "competition.dex_factor_result.v1"
        or result.get("protocol_sha256") != digest(spec_path)
        or result.get("manifest_sha256") != digest(safe_path(protocol["manifest_file"]))
        or result.get("dataset") != protocol["dataset"]
        or result.get("source_commit") != protocol["source_commit"]
    ):
        raise ValueError("FACTOR_RESULT_MISMATCH")
    return envelope(
        "factors",
        projects=[
            {
                "status": "completed",
                "role": "retrospective",
                "result": str(output / "result.json"),
            }
        ],
    )
