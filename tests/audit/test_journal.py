from __future__ import annotations

from packages.audit import EventJournal


def test_append_is_idempotent_and_projection_rebuilds(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    event = {"event_id": "e1", "kind": "order_submitted", "order_id": "o1"}
    assert journal.append(event) is True
    assert journal.append(event) is False
    journal.append({"event_id": "e2", "kind": "order_status", "order_id": "o1", "status": "filled"})
    assert journal.rebuild_projection()["o1"]["status"] == "filled"
    assert len(journal.read()) == 2
