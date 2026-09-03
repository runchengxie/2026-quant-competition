from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_EVIDENCE_FIELDS = frozenset({"run_id", "strategy_id", "environment", "started_at", "events_file"})


def validate_release_evidence(evidence: Mapping[str, Any]) -> None:
    missing = REQUIRED_EVIDENCE_FIELDS - set(evidence)
    if missing:
        raise ValueError(f"missing evidence fields: {sorted(missing)!r}")
    serialized = json.dumps(evidence, ensure_ascii=False).lower()
    if any(token in serialized for token in ("api_key", "secret", "password", "access_key")):
        raise ValueError("evidence must not contain credentials")
    if evidence["environment"] == "paper" and evidence.get("live_enabled") is True:
        raise ValueError("paper evidence cannot enable live trading")


def write_release_evidence(path: str | Path, evidence: Mapping[str, Any]) -> Path:
    validate_release_evidence(evidence)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
