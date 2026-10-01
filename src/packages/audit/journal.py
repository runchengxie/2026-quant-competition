from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


class EventJournal:
    """Append-only JSONL journal with event-id idempotency."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict) or not value.get("event_id"):
                    raise ValueError("journal entries require event_id")
                events.append(value)
        return events

    def append(self, event: Mapping[str, Any]) -> bool:
        value = dict(event)
        event_id = value.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id is required")
        if event_id in {item["event_id"] for item in self.read()}:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True

    def rebuild_projection(self) -> dict[str, dict[str, Any]]:
        projection: dict[str, dict[str, Any]] = {}
        for event in self.read():
            order_id = event.get("order_id")
            if isinstance(order_id, str) and order_id:
                current = projection.setdefault(order_id, {"order_id": order_id})
                current.update(event)
        return projection
