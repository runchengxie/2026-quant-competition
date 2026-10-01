from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    unknown_order_ids: tuple[str, ...]
    missing_broker_order_ids: tuple[str, ...]
    unjournaled_broker_order_ids: tuple[str, ...]


_TERMINAL = {"filled", "cancelled", "rejected", "inactive"}


def reconcile_orders(
    journal_events: Sequence[Mapping[str, Any]],
    *,
    broker_orders: Sequence[Mapping[str, Any]],
) -> ReconciliationReport:
    journal_ids = {
        str(event["order_id"])
        for event in journal_events
        if event.get("order_id") is not None
    }
    terminal: dict[str, str] = {}
    for event in journal_events:
        order_id = event.get("order_id")
        status = event.get("status")
        if order_id is not None and isinstance(status, str):
            terminal[str(order_id)] = status.lower()
    submitted = {
        str(event["order_id"])
        for event in journal_events
        if event.get("kind") == "order_submitted" and event.get("order_id") is not None
    }
    broker_ids = {str(order["order_id"]) for order in broker_orders if order.get("order_id") is not None}
    return ReconciliationReport(
        unknown_order_ids=tuple(sorted(order_id for order_id in submitted if terminal.get(order_id) not in _TERMINAL)),
        missing_broker_order_ids=tuple(sorted(submitted - broker_ids)),
        unjournaled_broker_order_ids=tuple(sorted(broker_ids - journal_ids)),
    )
