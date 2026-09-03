"""Broker-neutral execution boundary used by the Windows runner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from packages.contracts import TargetSet

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


class SubmissionPort(Protocol):
    """Future broker adapter interface; implemented in Task 4."""

    def submit(self, candidates: tuple[ExecutionCandidate, ...]) -> None: ...


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
    ) -> None:
        self.settings = settings
        self.submission_port = submission_port

    def run(self, target_set: TargetSet) -> ExecutionRunResult:
        """Prepare execution candidates and return a safe, observable result."""

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
        return ExecutionRunResult(
            status="blocked",
            submitted=False,
            broker_call_attempted=False,
            candidates=candidates,
            message=(
                "external submission is unavailable until the Task 4 IBKR event "
                "adapter, risk checks, and event journal are installed"
            ),
        )
