"""Dataset operations are explicit and separate from research promotion."""

from pathlib import Path
import os

from .config import TeamConfig
from .paths import validate_external
from .processes import envelope, child_environment
from competition_tools.datasets.spec import load_spec
from competition_tools.datasets.providers import readiness
from competition_tools.datasets.quality import inspect_dataset
from competition_tools.datasets.storage import publish_dataset, write_manifest


def execute(
    action: str,
    config: TeamConfig,
    spec_path: Path,
    manifest_path: Path | None = None,
    *,
    ensure_gateway: bool = False,
    gateway_config: Path | None = None,
    gateway_workspace: Path | None = None,
    gateway_wrapper: Path | None = None,
    base_manifest: Path | None = None,
) -> dict:
    spec = load_spec(validate_external(spec_path))
    if spec.get("schema") == "competition.databento_dataset_spec.v1":
        from .databento import execute as execute_databento

        if (ensure_gateway or gateway_config or gateway_workspace or gateway_wrapper
            or base_manifest is not None or action == "refresh"):
            raise ValueError("UNSUPPORTED_DATABENTO_OPTIONS")
        return execute_databento(action, config, spec, manifest_path)
    if ensure_gateway and (action != "acquire" or spec["source"] != "ibkr"):
        raise ValueError(
            "Gateway startup is only available for explicit IBKR acquisition"
        )
    if not ensure_gateway and any(
        p is not None for p in (gateway_config, gateway_workspace, gateway_wrapper)
    ):
        raise ValueError("Gateway arguments require explicit opt-in")
    if spec["schema"] == "competition.dex_dataset_spec.v1":
        return _execute_dex(action, config, spec, manifest_path, base_manifest)
    if spec["schema"] == "competition.dataset_spec.v2":
        return _execute_daily(action, config, spec, manifest_path, base_manifest)
    if action == "refresh" or base_manifest is not None:
        raise ValueError("REFRESH_REQUIRES_V2")
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
        config.storage_root
        / "datasets"
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
    gateway_status = None
    try:
        if ensure_gateway:
            from .gateway import ensure_gateway as ensure

            gateway_status = ensure(
                Path(spec["credential_file"]),
                launcher_config=gateway_config,
                workspace=gateway_workspace,
                wrapper=gateway_wrapper,
                environment=child_environment(config),
            )
            if gateway_status["state"] != "ready":
                return envelope(
                    "data", issues=[gateway_status["code"]], projects=[gateway_status]
                )
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
        projects=([gateway_status] if gateway_status is not None else [])
        + [
            {
                "status": receipt["status"],
                "receipt": str(manifest),
                "coverage": receipt["coverage"],
                "gaps": receipt["gaps"],
            }
        ],
    )


def _execute_dex(action, config, spec, manifest_path, base_manifest):
    from competition_tools.datasets.dex_provider import plan_dex
    from competition_tools.datasets.dex_acquisition import acquire_dex, resume_state
    from competition_tools.datasets.dex_storage import publish_dex, inspect_dex
    from competition_tools.datasets.dex_spec import safe_path
    from competition_tools.datasets.dex_transport import DexTransport

    if action == "refresh" or base_manifest is not None:
        raise ValueError("DEX_REFRESH_UNSUPPORTED")
    if action == "plan":
        return envelope("data", projects=[plan_dex(spec)])
    if action == "inspect":
        if manifest_path is None:
            raise ValueError("MANIFEST_REQUIRED")
        return envelope("data", projects=[inspect_dex(manifest_path)])
    if action != "acquire":
        raise ValueError("INVALID_DATA_ACTION")
    destination = safe_path(config.storage_root / "datasets" / spec["dataset_id"] / spec["version"])
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
        prior = resume_state(spec, staging)
        budget = dict(spec["budget"])
        if prior:
            import math
            for key, used in prior["spent"].items():
                budget[key] -= math.ceil(used)
                if budget[key] <= 0:
                    raise ValueError("RESUME_BUDGET_EXHAUSTED")
        segment = len(list(staging.glob("requests-*.jsonl"))) + 1
        transport = DexTransport(budget, Path(spec["credential_file"]), staging / f"requests-{segment}.jsonl")
        receipt = acquire_dex(spec, staging, transport=transport)
        if receipt["status"] in {"completed", "partial"}:
            publish_dex(staging, destination)
            manifest = destination / "manifest.json"
        else:
            manifest = staging / "manifest.json"
    finally:
        os.close(fd)
        lock.unlink()
    return envelope("data", issues=receipt["issues"] + ([] if receipt["status"] == "completed" else ["PARTIAL_DEX_COVERAGE"]),
                    projects=[{"status": receipt["status"], "manifest": str(manifest), "coverage": receipt["coverage"]}])


def _execute_daily(action, config, spec, manifest_path, base_manifest):
    from competition_tools.datasets.daily_broker import collect_daily
    from competition_tools.datasets.daily_refresh import refresh_daily
    from competition_tools.datasets.daily_storage import safe_path, write_daily_manifest, verify_daily_manifest

    if action == "inspect":
        if manifest_path is None:
            raise ValueError("MANIFEST_REQUIRED")
        return envelope("data", projects=[inspect_dataset(manifest_path)])
    if (action == "refresh") != (base_manifest is not None):
        raise ValueError("EXPLICIT_REFRESH_PARENT_REQUIRED")
    if action == "plan":
        return envelope("data", projects=[{"status":"ready", "source":"ibkr_daily", "kind":"bounded_daily_equity", "budget":spec["budget"], "entitlement":"not_checked"}])
    if action not in {"acquire", "refresh"}:
        raise ValueError("INVALID_DATA_ACTION")
    destination = safe_path(config.storage_root / "datasets" / spec["dataset_id"] / spec["version"])
    if destination.exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = safe_path(destination.with_name(destination.name + ".acquire-lock"))
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("ACQUISITION_IN_PROGRESS") from None
    staging = destination.with_name(destination.name + ".partial")
    try:
        if (staging / "manifest.json").exists():
            manifest = verify_daily_manifest(staging / "manifest.json")
            from competition_tools.datasets.storage import spec_hash
            if manifest["spec_hash"] != spec_hash(spec) or manifest["status"] != "acquired":
                raise ValueError("INVALID_COMPLETED_STAGING")
            receipt = manifest["receipt"]
        else:
            receipt = refresh_daily(spec, base_manifest, staging) if action == "refresh" else collect_daily(spec, staging)
            if receipt["status"] == "acquired":
                write_daily_manifest(spec, staging, receipt, parent_sha256=receipt["parent_manifest_sha256"])
        if receipt["status"] == "acquired":
            staging.rename(destination)
            artifact = destination / "manifest.json"
        else:
            # Owned checkpoints may resume. Only a completed snapshot gets an
            # immutable manifest; partial attempt evidence stays in receipt.json.
            artifact = staging / "receipt.json"
    finally:
        os.close(fd)
        lock.unlink()
    return envelope("data", issues=[] if receipt["status"] == "acquired" else ["PARTIAL_COVERAGE", *receipt["issue_codes"]], projects=[{"status":receipt["status"], "receipt":str(artifact), "coverage":receipt["coverage"], "gaps":receipt["gaps"]}])
