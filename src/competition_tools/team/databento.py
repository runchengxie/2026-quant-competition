"""Dispatch the isolated Databento ingestion contract without study promotion."""

from pathlib import Path

from competition_tools.datasets.databento_acquisition import acquire, verify_manifest
from competition_tools.datasets.databento_spec import plan, safe_path
from .config import TeamConfig
from .processes import envelope


def execute(
    action: str, config: TeamConfig, spec: dict, manifest_path: Path | None
) -> dict:
    if action == "plan":
        if manifest_path is not None:
            raise ValueError("UNSUPPORTED_DATABENTO_OPTIONS")
        return envelope("data", projects=[plan(spec)])
    if action == "inspect":
        if manifest_path is None:
            raise ValueError("MANIFEST_REQUIRED")
        value = verify_manifest(manifest_path)
        if value["spec"] != spec:
            raise ValueError("MANIFEST_SPEC_MISMATCH")
        result = {**value["receipt"], "manifest": str(manifest_path)}
    elif action == "acquire":
        if manifest_path is not None:
            raise ValueError("UNSUPPORTED_DATABENTO_OPTIONS")
        destination = safe_path(
            config.data_root
            / "2026-quant-competition/datasets"
            / spec["dataset_id"]
            / spec["version"]
        )
        result = acquire(spec, destination)
    else:
        raise ValueError("UNSUPPORTED_DATABENTO_OPERATION")
    return envelope("data", issues=result["issue_codes"], projects=[result])
