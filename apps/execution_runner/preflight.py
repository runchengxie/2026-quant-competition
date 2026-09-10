from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from packages.contracts import TargetSet
from strategies.nira.handoff import HandoffValidationError, load_target_artifact

from .config import ConfigurationError, resolve_runner_settings
from .runner import ExecutionRunner


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    status: str
    message: str
    details: Mapping[str, Any] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "message": self.message, "details": dict(self.details)}


@dataclass(frozen=True, slots=True)
class PreflightReport:
    overall: str
    checks: tuple[PreflightCheck, ...]

    def check(self, name: str) -> PreflightCheck:
        return next(item for item in self.checks if item.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {"overall": self.overall, "checks": [item.to_dict() for item in self.checks]}


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _check_gateway(host: str, port: int, timeout: float) -> PreflightCheck:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return PreflightCheck("gateway", "pass", "Gateway TCP endpoint is reachable", {"host": host, "port": port})
    except OSError as exc:
        return PreflightCheck("gateway", "blocked", "Gateway TCP endpoint is not reachable; no order request was made", {"host": host, "port": port, "error": str(exc)})


def _risk_check(target_set: TargetSet, config: Mapping[str, Any]) -> PreflightCheck:
    portfolio = config.get("portfolio", {})
    max_weight = Decimal(str(portfolio.get("max_single_weight", 1)))
    offenders = [target.symbol for target in target_set.targets if target.weight > max_weight]
    if offenders:
        return PreflightCheck("target_risk", "fail", "target exceeds configured maximum single weight", {"max_single_weight": str(max_weight), "offenders": offenders})
    return PreflightCheck("target_risk", "pass", "target weights are within configured single-name limit", {"target_count": len(target_set.targets), "weight_sum": str(sum((item.weight for item in target_set.targets), Decimal("0")))})


def run_preflight(
    targets_path: str | Path,
    config_path: str | Path,
    *,
    positions: Mapping[str, Decimal] | None = None,
    check_gateway: bool = False,
    gateway_timeout: float = 2.0,
    environment: Mapping[str, str] | None = None,
) -> PreflightReport:
    config = _read_json(config_path)
    checks: list[PreflightCheck] = []
    try:
        execution = config.get("execution", {})
        settings = resolve_runner_settings(config=execution, environment=environment)
        if settings.environment != "paper" or not settings.dry_run:
            raise ConfigurationError("preflight requires environment=paper and dry_run=true")
        checks.append(PreflightCheck("execution_safety", "pass", "Paper and dry-run safety gates are enabled", {"environment": settings.environment, "dry_run": settings.dry_run, "gateway_port": settings.gateway_port}))
    except (ConfigurationError, TypeError, ValueError) as exc:
        checks.append(PreflightCheck("execution_safety", "fail", str(exc)))
        settings = None

    handoff = None
    try:
        handoff = load_target_artifact(targets_path)
        expected_market = config.get("market")
        if expected_market and handoff.target_set.market.value != expected_market:
            raise HandoffValidationError(f"target market {handoff.target_set.market.value} does not match config market {expected_market}")
        checks.append(PreflightCheck("target_handoff", "pass", "target and lineage artifact validated", {"strategy_id": handoff.target_set.strategy_id, "market": handoff.target_set.market.value, "target_count": len(handoff.target_set.targets)}))
        checks.append(_risk_check(handoff.target_set, config))
    except (OSError, ValueError, HandoffValidationError, TypeError) as exc:
        checks.append(PreflightCheck("target_handoff", "fail", str(exc)))
        checks.append(PreflightCheck("target_risk", "skipped", "target risk check skipped because handoff failed"))

    if settings is not None and handoff is not None and all(item.status == "pass" for item in checks if item.name in {"execution_safety", "target_handoff", "target_risk"}):
        try:
            result = ExecutionRunner(settings, journal_path=Path(config_path).with_name("preflight-events.jsonl")).run_rebalance(handoff.target_set, positions or {})
            status = "pass" if result.status == "dry_run" and not result.broker_call_attempted and not result.submitted else "fail"
            checks.append(PreflightCheck("dry_run_rebalance", status, result.message, {"intent_count": len(result.intents), "broker_call_attempted": result.broker_call_attempted, "submitted": result.submitted}))
        except (TypeError, ValueError) as exc:
            checks.append(PreflightCheck("dry_run_rebalance", "fail", f"dry-run rebalance could not be planned: {exc}"))
    else:
        checks.append(PreflightCheck("dry_run_rebalance", "skipped", "dry-run rebalance skipped because safety or handoff checks failed"))

    if check_gateway and settings is not None:
        checks.append(_check_gateway(settings.gateway_host, settings.gateway_port, gateway_timeout))
    else:
        checks.append(PreflightCheck("gateway", "skipped", "Gateway check not requested; no network call was made"))

    overall = "fail" if any(item.status == "fail" for item in checks) else ("blocked" if any(item.status == "blocked" for item in checks) else "pass")
    return PreflightReport(overall, tuple(checks))
