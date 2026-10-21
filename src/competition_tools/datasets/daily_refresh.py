"""New-version refresh with explicit parent hashes and revision rebuilding."""

import json
import shutil
import time
from pathlib import Path

from competition_tools.team.paper_session import PaperReadSession
from .daily_spec import validate_daily_spec
from .daily_storage import OWNER, safe_path, verify_daily_manifest, payload_files
from .daily_broker import _collect_daily, collection_lock
from .storage import digest, spec_hash, write_json


def refresh_daily(
    spec: dict,
    base_manifest: Path,
    staging: Path,
    *,
    session_factory=PaperReadSession,
    clock=time.monotonic,
    sleep=time.sleep,
) -> dict:
    with collection_lock(staging):
        return _refresh(
            spec,
            base_manifest,
            staging,
            session_factory=session_factory,
            clock=clock,
            sleep=sleep,
        )


def _refresh(spec, base_manifest, staging, *, session_factory, clock, sleep):
    preparation_started = clock()
    validate_daily_spec(spec)
    base_manifest = safe_path(base_manifest)
    base = verify_daily_manifest(base_manifest)
    parent_hash = digest(base_manifest)
    parent_spec = base["spec"]
    identity = set(parent_spec) - {"version", "end", "budget"}
    if (
        spec["version"] == base["version"]
        or spec["end"] < parent_spec["end"]
        or any(spec[k] != parent_spec[k] for k in identity)
    ):
        raise ValueError("REFRESH_IDENTITY_MISMATCH")
    if base["status"] != "acquired":
        raise ValueError("REFRESH_REQUIRES_COMPLETE_PARENT")
    if base["receipt"]["retained_payload_bytes"] > spec["budget"]["bytes"]:
        raise ValueError("REFRESH_BASE_EXCEEDS_BYTE_BUDGET")
    staging = safe_path(staging)
    checkpoint = staging / "checkpoint.json"
    if not staging.exists():
        staging.mkdir(parents=True)
        (staging / ".dataset-owner").write_text(OWNER)
        for directory in ("raw", "normalized"):
            (staging / directory).mkdir()
        for record in base["files"]:
            shutil.copyfile(
                base_manifest.parent / record["path"], staging / record["path"]
            )
        if digest(base_manifest) != parent_hash:
            raise ValueError("PARENT_CHANGED")
        parent_sessions = base["receipt"]["calendar"]["sessions"]
        state = {
            "spec_hash": spec_hash(spec),
            "requests": 0,
            "elapsed_seconds": 0,
            "done": [],
            "files": payload_files(staging),
            "resolved_contracts": base["receipt"]["resolved_contracts"],
            "refresh": {
                "parent_sha256": parent_hash,
                "overlap_start": parent_sessions[-min(5, len(parent_sessions))],
                "last_full_verification": base["receipt"]["adjustment_evidence"][
                    "last_full_verification"
                ],
            },
            "revisions": [],
            "rebuild_products": [],
            "excluded_non_session_bars": base["receipt"].get(
                "excluded_non_session_bars", []
            ),
        }
        write_json(checkpoint, state)
    else:
        state = json.loads(safe_path(checkpoint).read_text())
        if state.get("refresh", {}).get("parent_sha256") != parent_hash:
            raise ValueError("REFRESH_PARENT_MISMATCH")
    state["elapsed_seconds"] += max(0, clock() - preparation_started)
    write_json(checkpoint, state)
    receipt = _collect_daily(
        spec, staging, session_factory=session_factory, clock=clock, sleep=sleep
    )
    if digest(base_manifest) != parent_hash:
        raise ValueError("PARENT_CHANGED")
    receipt["parent_manifest_sha256"] = parent_hash
    receipt["overlap_sessions"] = 5
    write_json(staging / "receipt.json", receipt)
    return receipt
