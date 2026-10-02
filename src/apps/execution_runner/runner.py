"""Broker-neutral execution boundary used by the Windows runner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from typing import Protocol
from collections.abc import Mapping

from packages.audit import EventJournal
from .safety import KillSwitch
from packages.contracts import TargetSet, TargetValidationError

from .config import RunnerSettings


@dataclass(frozen=True, slots=True)
class ExecutionCandidate:
    """A target prepared for later risk checks and broker translation."""

    symbol: str
    weight: Decimal
    quantity: Decimal | None


@dataclass(frozen=True, slots=True)
class ExecutionRunResult:
    """An explicit result that never mistakes preparation for broker acceptance."""

    status: str
    submitted: bool
    broker_call_attempted: bool
    candidates: tuple[ExecutionCandidate, ...]
    message: str
    intents: tuple[object, ...] = ()


class SubmissionPort(Protocol):
    """Future broker adapter interface; implemented in Task 4."""

    def submit(self, candidates: tuple[ExecutionCandidate, ...]) -> None: ...


def _require_v1(target_set: TargetSet) -> None:
    if not isinstance(target_set, TargetSet) or target_set.schema_version != "1.0":
        raise TargetValidationError("execution requires a v1 TargetSet")


class ExecutionRunner:
    """Prepare contract targets without coupling the runner to a broker SDK.

    This task intentionally has no submission implementation.  That prevents
    a Paper configuration from becoming an accidental external order before
    the IBKR event adapter, risk checks, and event journal exist.
    """

    def __init__(
        self,
        settings: RunnerSettings,
        *,
        submission_port: SubmissionPort | None = None,
        journal_path: str | Path | None = None,
        run_id: str | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.settings = settings
        self.submission_port = submission_port
        self.journal = EventJournal(journal_path) if journal_path is not None else EventJournal("runs/events.jsonl")
        self.run_id = run_id or str(uuid4())
        self.kill_switch = kill_switch

    def run(self, target_set: TargetSet) -> ExecutionRunResult:
        """Prepare execution candidates and return a safe, observable result."""

        _require_v1(target_set)
        candidates = tuple(
            ExecutionCandidate(
                symbol=target.symbol,
                weight=target.weight,
                quantity=target.quantity,
            )
            for target in target_set.targets
        )
        if self.settings.dry_run:
            return ExecutionRunResult(
                status="dry_run",
                submitted=False,
                broker_call_attempted=False,
                candidates=candidates,
                message="dry-run prepared candidates; no broker submission was attempted",
            )
        if self.submission_port is not None:
            if self.kill_switch is not None:
                self.kill_switch.assert_clear()
            event_id = str(uuid4())
            self.journal.append({
                "event_id": event_id, "kind": "order_submitted", "run_id": self.run_id,
                "order_id": f"{self.run_id}:batch", "symbols": [item.symbol for item in candidates],
            })
            try:
                self.submission_port.submit(candidates)
            except Exception as exc:
                self.journal.append({
                    "event_id": str(uuid4()), "kind": "order_error", "run_id": self.run_id,
                    "order_id": f"{self.run_id}:batch", "message": str(exc),
                })
                return ExecutionRunResult(
                    status="unknown", submitted=False, broker_call_attempted=True,
                    candidates=candidates,
                    message="submission outcome is unknown; reconcile with broker before retrying",
                )
            return ExecutionRunResult(
                status="submitted", submitted=True, broker_call_attempted=True,
                candidates=candidates, message="submission request sent through the configured adapter",
            )
        return ExecutionRunResult(
            status="blocked",
            submitted=False,
            broker_call_attempted=False,
            candidates=candidates,
            message=(
                "external submission requires a configured broker adapter"
            ),
        )

    def run_rebalance(
        self, target_set: TargetSet, positions: Mapping[str, Decimal]
    ) -> ExecutionRunResult:
        """Plan target deltas, then optionally submit them through an adapter."""
        _require_v1(target_set)
        from packages.execution_policies.rebalance import plan_rebalance

        candidates = tuple(
            ExecutionCandidate(target.symbol, target.weight, target.quantity)
            for target in target_set.targets
        )
        intents = plan_rebalance(candidates, positions)
        if self.settings.dry_run:
            return ExecutionRunResult(
                status="dry_run", submitted=False, broker_call_attempted=False,
                candidates=candidates, message="dry-run planned rebalance intents",
                intents=intents,
            )
        submit_intents = getattr(self.submission_port, "submit_intents", None)
        if not callable(submit_intents):
            return ExecutionRunResult(
                status="blocked", submitted=False, broker_call_attempted=False,
                candidates=candidates,
                message="rebalance submission requires an adapter with submit_intents",
                intents=intents,
            )
        if self.kill_switch is not None:
            self.kill_switch.assert_clear()
        try:
            submit_intents(intents)
        except Exception as exc:
            self.journal.append({
                "event_id": str(uuid4()), "kind": "order_error", "run_id": self.run_id,
                "order_id": f"{self.run_id}:rebalance", "message": str(exc),
            })
            return ExecutionRunResult(
                status="unknown", submitted=False, broker_call_attempted=True,
                candidates=candidates,
                message="rebalance outcome is unknown; reconcile with broker before retrying",
                intents=intents,
            )
        return ExecutionRunResult(
            status="submitted", submitted=True, broker_call_attempted=True,
            candidates=candidates, message="rebalance intents submitted through adapter",
            intents=intents,
        )
