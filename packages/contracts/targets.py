"""Typed target portfolio contract consumed by the execution side."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from packages.market_model import Market, SymbolError, normalize_symbol, validate_quantity


class TargetValidationError(ValueError):
    """Raised when a target artifact is unsafe or structurally invalid."""


@dataclass(frozen=True, slots=True)
class Target:
    symbol: str
    weight: Decimal
    quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class TargetSet:
    schema_version: str
    strategy_id: str
    market: Market
    as_of: datetime
    targets: tuple[Target, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TargetSet":
        if not isinstance(payload, Mapping):
            raise TargetValidationError("target payload must be an object")

        schema_version = payload.get("schema_version")
        if schema_version != "1.0":
            raise TargetValidationError("unsupported schema_version")

        strategy_id = payload.get("strategy_id")
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise TargetValidationError("strategy_id is required")

        try:
            market = Market(payload.get("market"))
        except ValueError as exc:
            raise TargetValidationError("market must be a supported market") from exc

        as_of = _parse_utc(payload.get("as_of"))
        raw_targets = payload.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise TargetValidationError("at least one target is required")

        targets: list[Target] = []
        symbols: set[str] = set()
        for raw_target in raw_targets:
            if not isinstance(raw_target, Mapping):
                raise TargetValidationError("each target must be an object")
            try:
                instrument = normalize_symbol(str(raw_target.get("symbol", "")))
            except SymbolError as exc:
                raise TargetValidationError(str(exc)) from exc
            if instrument.market is not market:
                raise TargetValidationError(
                    f"target symbol {instrument.symbol} does not belong to market {market.value}"
                )
            if instrument.symbol in symbols:
                raise TargetValidationError(f"duplicate symbol: {instrument.symbol}")
            symbols.add(instrument.symbol)

            weight = _parse_decimal(raw_target.get("weight"), "weight")
            if not Decimal("0") <= weight <= Decimal("1"):
                raise TargetValidationError("weight must be between 0 and 1")

            quantity = None
            if "quantity" in raw_target and raw_target["quantity"] is not None:
                quantity = _parse_decimal(raw_target["quantity"], "quantity")
                try:
                    quantity = validate_quantity(instrument, quantity)
                except ValueError as exc:
                    raise TargetValidationError(str(exc)) from exc

            targets.append(Target(instrument.symbol, weight, quantity))

        return cls(
            schema_version=schema_version,
            strategy_id=strategy_id.strip(),
            market=market,
            as_of=as_of,
            targets=tuple(targets),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize without converting decimal fields to binary floats."""

        return {
            "schema_version": self.schema_version,
            "strategy_id": self.strategy_id,
            "market": self.market.value,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "targets": [
                {
                    "symbol": target.symbol,
                    "weight": str(target.weight),
                    **({"quantity": str(target.quantity)} if target.quantity is not None else {}),
                }
                for target in self.targets
            ],
        }


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TargetValidationError("as_of must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TargetValidationError("as_of must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TargetValidationError("as_of must include a UTC timezone")
    if parsed.utcoffset().total_seconds() != 0:
        raise TargetValidationError("as_of must be UTC")
    return parsed.astimezone(UTC)


def _parse_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise TargetValidationError(f"{field} must be a decimal value")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TargetValidationError(f"{field} must be a decimal value") from exc
    if not parsed.is_finite():
        raise TargetValidationError(f"{field} must be finite")
    return parsed
