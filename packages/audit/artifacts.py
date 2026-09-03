from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from strategies.nira.handoff import NiraTargetHandoff
from .evidence import validate_release_evidence


def publish_frozen_run(
    run_root: str | Path, *, targets: Mapping[str, Any],
    lineage: Mapping[str, Any], config: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> Path:
    """Write a complete, immutable competition run directory."""
    handoff = NiraTargetHandoff.from_payload(targets, lineage)
    execution = config.get("execution", {})
    if not isinstance(execution, Mapping):
        raise ValueError("config.execution must be an object")
    environment = str(execution.get("environment", "paper"))
    evidence = {
        "run_id": Path(run_root).name,
        "strategy_id": handoff.target_set.strategy_id,
        "environment": environment,
        "started_at": datetime.now(UTC).isoformat(),
        "events_file": "events.jsonl",
        "live_enabled": environment == "live",
    }
    validate_release_evidence(evidence)
    root = Path(run_root)
    if root.exists():
        raise FileExistsError(f"refusing to overwrite existing run: {root}")
    root.mkdir(parents=True)
    documents = {
        "targets.json": handoff.to_target_dict(),
        "lineage.json": handoff.to_lineage_dict(),
        "resolved-config.json": dict(config),
        "metrics.json": dict(metrics),
        "evidence.json": evidence,
    }
    try:
        for name, payload in documents.items():
            (root / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except BaseException:
        for path in root.iterdir():
            path.unlink()
        root.rmdir()
        raise
    return root
