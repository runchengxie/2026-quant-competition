"""Frozen-identity hourly acquisition with durable checkpoints and bounded resume."""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from .dex_protocol import load_factor_protocol
from .dex_spec import safe_path, validate_dex_spec, dataset_identity
from .dex_provider import plan_dex, usage_preflight, require_headroom, UNITS_SOURCE
from .dex_quality import normalize_chunk, validate_hourly_rows, UNITS
from .dex_storage import OWNER, read_json, file_records, write_dex_manifest
from .storage import digest, spec_hash, write_json


def resume_state(spec, staging):
    """Verify all previous bytes; an uncertain interrupted request cannot reset spend."""
    staging = safe_path(staging)
    if not staging.exists():
        return None
    owner = staging / ".dataset-owner"
    if not owner.is_file() or owner.read_text() != OWNER:
        raise ValueError("UNOWNED_STAGING")
    path = staging / "receipt.json"
    if not path.is_file():
        raise ValueError("UNKNOWN_SPENT_BUDGET")
    receipt = read_json(path)
    if receipt["spec_sha256"] != spec_hash(spec):
        raise ValueError("CHANGED_DEX_SPEC")
    actual = [r for r in file_records(staging) if r["path"] != "receipt.json"]
    if actual != receipt["checkpoints"]:
        raise ValueError("RESUME_HASH_OR_BUDGET_MISMATCH")
    if receipt["status"] in {"completed", "partial"}:
        raise ValueError("DATASET_ALREADY_COLLECTED")
    return receipt


def acquire_dex(spec: dict, staging: Path, *, transport) -> dict:
    validate_dex_spec(spec)
    plan = plan_dex(spec)
    if not plan["fits_budget"]:
        raise ValueError("PLANNED_REQUEST_BUDGET")
    staging = safe_path(staging)
    protocol_path = safe_path(spec["protocol_file"])
    if digest(protocol_path) != spec["protocol_sha256"]:
        raise ValueError("PROTOCOL_HASH_MISMATCH")
    protocol = load_factor_protocol(protocol_path)
    planned = safe_path(protocol["manifest_file"]).parent
    if staging not in {planned, planned.with_name(planned.name + ".partial")}:
        raise ValueError("PROTOCOL_MANIFEST_MISMATCH")
    if protocol.get("dataset") != dataset_identity(spec):
        raise ValueError("PROTOCOL_DATASET_MISMATCH")
    prior = resume_state(spec, staging)
    if not transport.ledger.is_relative_to(staging) or transport.ledger.exists():
        raise ValueError("INVALID_DEX_LEDGER")
    staging.mkdir(parents=True, exist_ok=True)
    lock = staging / ".acquiring"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("ACQUISITION_IN_PROGRESS") from None
    try:
        return _collect(spec, staging, transport, plan, prior)
    finally:
        os.close(fd)
        lock.unlink()


def _collect(spec, staging, transport, plan, prior):
    if prior is None:
        (staging / ".dataset-owner").write_text(OWNER)
        (staging / "protocol.json").write_bytes(
            safe_path(spec["protocol_file"]).read_bytes()
        )
    for name in ("raw", "normalized"):
        (staging / name).mkdir(exist_ok=True)
    spent = prior["spent"] if prior else {"requests": 0, "bytes": 0, "seconds": 0}
    if any(transport.budget[k] > spec["budget"][k] - spent[k] for k in spent):
        raise ValueError("RESUME_BUDGET_NOT_REDUCED")
    receipt = {
        "schema": "competition.dex_dataset_receipt.v1",
        "spec_sha256": spec_hash(spec),
        "protocol_sha256": spec["protocol_sha256"],
        "status": "blocked",
        "coverage": [],
        "snapshots": prior["snapshots"][:] if prior else [],
        "spent": spent.copy(),
        "units": UNITS,
        "units_source": UNITS_SOURCE,
        "issues": [],
        "checkpoints": [],
        "completed_resources": prior["completed_resources"][:] if prior else [],
    }
    completed = set(receipt["completed_resources"])
    start = transport.started
    if prior:
        for record in prior["checkpoints"]:
            if record["path"].endswith(".jsonl"):
                for line in (
                    (staging / record["path"]).read_text(encoding="utf-8").splitlines()
                ):
                    entry = json.loads(line)
                    if (
                        entry.get("endpoint") != "usage"
                        and entry.get("status") == "interrupted"
                    ):
                        resource = entry.get("resource")
                        if not isinstance(resource, str):
                            raise ValueError("UNKNOWN_RESOURCE_ATTEMPTS")
                        transport.resource_attempts[resource] = max(
                            transport.resource_attempts.get(resource, 0),
                            entry["attempt"],
                        )

    def checkpoint():
        receipt["spent"] = {
            "requests": spent["requests"] + transport.requests,
            "bytes": spent["bytes"] + transport.bytes,
            "seconds": spent["seconds"] + max(0, transport.clock() - start),
        }
        if receipt["spent"]["seconds"] >= spec["budget"]["seconds"]:
            receipt["status"] = "blocked"
            if "TIME_BUDGET" not in receipt["issues"]:
                receipt["issues"].append("TIME_BUDGET")
        receipt["checkpoints"] = [
            r for r in file_records(staging) if r["path"] != "receipt.json"
        ]
        write_json(staging / "receipt.json", receipt)

    def usage(name):
        remaining = spec["budget"]["requests"] - spent["requests"] - transport.requests
        result = usage_preflight(transport, max(0, remaining - 1))
        write_json(staging / "raw" / (name + ".json"), transport.private_usage)
        checkpoint()
        if result["status"] != "allowed":
            raise ValueError(result["reason"])
        return result

    def fetch(name, endpoint, **kwargs):
        path = staging / "raw" / (name + ".json")
        if name in completed:
            return read_json(path)
        remaining = spec["budget"]["requests"] - spent["requests"] - transport.requests
        require_headroom(transport, remaining)
        value = transport.get_json(endpoint, **kwargs)
        write_json(path, value)
        completed.add(name)
        receipt["completed_resources"].append(name)
        checkpoint()
        return value

    checkpoint()
    try:
        usage("usage-initial-" + str(spent["requests"]))
        networks = fetch("networks", "networks")
        if not isinstance(networks, list) or not all(
            isinstance(n, dict) and isinstance(n.get("id"), str) for n in networks
        ):
            raise ValueError("NETWORK_CONTRACT_UNVERIFIED")
        known = {n["id"] for n in networks}
        for asset in spec["assets"]:
            asset_id = asset["stable_id"]
            usage("usage-" + asset_id + "-" + str(spent["requests"]))
            if asset["network"] not in known:
                raise ValueError("NETWORK_NOT_SUPPORTED")
            args = {"network": asset["network"], "address": asset["address"]}
            token = fetch(asset_id + "-metadata", "token", **args)
            if (
                not isinstance(token, dict)
                or token.get("id") != asset["address"]
                or token.get("chain") != asset["network"]
            ):
                raise ValueError("TOKEN_IDENTITY_MISMATCH")
            if "pool_address" in asset:
                pool = fetch(
                    asset_id + "-pool",
                    "pool",
                    network=asset["network"],
                    address=asset["pool_address"],
                )
                if (
                    not isinstance(pool, dict)
                    or pool.get("id") != asset["pool_address"]
                    or pool.get("chain") != asset["network"]
                    or not isinstance(pool.get("tokens"), list)
                    or not all(isinstance(p, dict) for p in pool["tokens"])
                    or not any(
                        p.get("id") == asset["address"]
                        and p.get("chain") == asset["network"]
                        for p in pool["tokens"]
                    )
                ):
                    raise ValueError("POOL_IDENTITY_MISMATCH")
                if not any(s["asset_id"] == asset_id for s in receipt["snapshots"]):
                    receipt["snapshots"].append(
                        {
                            "asset_id": asset_id,
                            "network": asset["network"],
                            "pool_address": asset["pool_address"],
                            "observed_at": datetime.now(timezone.utc).isoformat(),
                            "source": "dexpaprika",
                            "historical_coverage": False,
                        }
                    )
            rows, overlap = [], {}
            for index, chunk in enumerate(plan["chunks"]):
                raw = fetch(f"{asset_id}-{index}", "token_ohlcv", query=chunk, **args)
                normalized = normalize_chunk(
                    raw, asset_id=asset_id, start=chunk["start"], end=chunk["end"]
                )
                for row in raw:
                    timestamp = row["time_open"]
                    if timestamp in overlap and overlap[timestamp] != row:
                        raise ValueError("CHANGED_OVERLAP")
                    overlap[timestamp] = row
                rows.extend(normalized)
            coverage = validate_hourly_rows(
                rows, start=spec["start"], end=spec["end"], units=UNITS
            )
            receipt["coverage"].append({"asset_id": asset_id, **coverage})
            write_json(staging / "normalized" / (asset_id + ".json"), rows)
            checkpoint()
        usage("usage-final-" + str(spent["requests"]))
        receipt["status"] = (
            "completed"
            if all(c["status"] == "completed" for c in receipt["coverage"])
            else "partial"
        )
    except (ValueError, OSError, KeyError, TypeError):
        # Error text is never copied from provider exceptions or arbitrary payloads.
        import sys

        error = sys.exception()
        known_codes = {
            "TOKEN_IDENTITY_MISMATCH",
            "POOL_IDENTITY_MISMATCH",
            "CHANGED_OVERLAP",
            "NETWORK_NOT_SUPPORTED",
            "NETWORK_CONTRACT_UNVERIFIED",
            "INCLUDED_CREDITS_EXHAUSTED",
            "CREDIT_CONTRACT_UNVERIFIED",
            "CREDIT_USAGE_DISCONTINUITY",
            "TIME_BUDGET",
            "REQUEST_BUDGET",
            "BYTE_BUDGET",
            "RETRIES_EXHAUSTED",
            "OUT_OF_RANGE_CANDLE",
            "DUPLICATE_CANDLE",
            "INCOMPLETE_CANDLE",
            "INVALID_CANDLE_NUMBER",
            "INVALID_OHLC_ORDER",
            "INVALID_CANDLE_RESPONSE",
            "RESPONSE_SECRET_ECHO",
            "HTTP_401",
            "HTTP_403",
            "HTTP_404",
        }
        receipt["issues"] = [
            str(error) if str(error) in known_codes else "DEX_ACQUISITION_BLOCKED"
        ]
    finally:
        # Include empty/unfinished assets in coverage rather than dropping denominators.
        present = {c["asset_id"] for c in receipt["coverage"]}
        for asset in spec["assets"]:
            if asset["stable_id"] not in present:
                receipt["coverage"].append(
                    {
                        "asset_id": asset["stable_id"],
                        **validate_hourly_rows(
                            [], start=spec["start"], end=spec["end"], units=UNITS
                        ),
                    }
                )
        checkpoint()
        write_dex_manifest(spec, staging, receipt)
        # Charge finalization against the same active origin as network I/O.
        checkpoint()
        write_dex_manifest(spec, staging, receipt)
    return receipt
