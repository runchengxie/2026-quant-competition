"""Dataset operations are explicit and separate from research promotion."""

from pathlib import Path
import os

from .config import TeamConfig
from .paths import validate_external
from .processes import envelope
from competition_tools.datasets.spec import load_spec
from competition_tools.datasets.providers import readiness
from competition_tools.datasets.quality import inspect_dataset
from competition_tools.datasets.storage import publish_dataset, write_manifest


def execute(
    action: str, config: TeamConfig, spec_path: Path, manifest_path: Path | None = None
) -> dict:
    spec = load_spec(validate_external(spec_path))
    capability = readiness(spec)
    if action == "inspect":
        if manifest_path is None:
            raise ValueError("MANIFEST_REQUIRED")
        return envelope("data", projects=[inspect_dataset(manifest_path)])
    if capability["status"] == "blocked":
        return envelope("data", issues=[capability["reason"]], projects=[capability])
    if action == "plan":
        return envelope("data", projects=[capability | {"budget": spec["budget"]}])
    from competition_tools.datasets.acquisition import acquire

    destination = validate_external(
        config.data_root
        / "2026-quant-competition/datasets"
        / spec["dataset_id"]
        / spec["version"]
    )
    if destination.exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name(destination.name + ".acquire-lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("ACQUISITION_IN_PROGRESS") from None
    staging = destination.with_name(destination.name + ".partial")
    try:
        receipt = acquire(spec, staging)
        # Retain partial acquisition in owned staging so the same spec can resume.
        if receipt["status"] == "acquired":
            publish_dataset(spec, staging, destination)
            manifest = destination / "manifest.json"
        else:
            write_manifest(spec, staging)
            manifest = staging / "manifest.json"
    finally:
        os.close(fd)
        lock.unlink()
    return envelope(
        "data",
        issues=[] if receipt["status"] == "acquired" else ["PARTIAL_COVERAGE"],
        projects=[
            {
                "status": receipt["status"],
                "receipt": str(manifest),
                "coverage": receipt["coverage"],
                "gaps": receipt["gaps"],
            }
        ],
    )
