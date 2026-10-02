"""Explicit v2 interchange contract; not an input to the v1 execution runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
import re
from typing import Any, Mapping

from .targets import TargetValidationError


_COMMON = {"asset_type", "symbol", "market", "exchange_mic", "currency"}
_FUTURE = {
    "contract_month",
    "expiry_date",
    "multiplier",
    "tick_size",
    "roll_rule_id",
    "settlement_type",
    "margin_model_id",
}
_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_WEIGHT = re.compile(r"(?:0|0\.[0-9]+|1(?:\.0+)?)")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)"
)


@dataclass(frozen=True, slots=True)
class SecurityInstrumentV2:
    asset_type: str
    symbol: str
    market: str
    exchange_mic: str
    currency: str


@dataclass(frozen=True, slots=True)
class FuturesInstrumentV2:
    asset_type: str
    symbol: str
    market: str
    exchange_mic: str
    currency: str
    contract_month: str
    expiry_date: date
    multiplier: Decimal
    tick_size: Decimal
    roll_rule_id: str
    settlement_type: str
    margin_model_id: str


@dataclass(frozen=True, slots=True)
class TargetV2:
    instrument: SecurityInstrumentV2 | FuturesInstrumentV2
    weight: Decimal
    quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class TargetManifestV2:
    schema_version: str
    strategy_id: str
    as_of: datetime
    reporting_currency: str
    targets: tuple[TargetV2, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TargetManifestV2:
        root = _object(
            payload,
            {"schema_version", "strategy_id", "as_of", "reporting_currency", "targets"},
            "root",
        )
        if root["schema_version"] != "2.0":
            raise TargetValidationError("unsupported schema_version")
        strategy_id = _text(root["strategy_id"], "strategy_id")
        timestamp = _match(root["as_of"], _TIMESTAMP, "as_of UTC timestamp")
        try:
            as_of = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(
                UTC
            )
        except ValueError as exc:
            raise TargetValidationError("as_of must be a valid UTC timestamp") from exc
        currency = _match(root["reporting_currency"], r"[A-Z]{3}", "reporting_currency")
        raw_targets = root["targets"]
        if not isinstance(raw_targets, list) or not raw_targets:
            raise TargetValidationError("at least one target is required")

        targets: list[TargetV2] = []
        seen: set[tuple[str, ...]] = set()
        for raw in raw_targets:
            item = _object(
                raw, {"instrument", "weight"}, "target", optional={"quantity"}
            )
            instrument = _instrument(item["instrument"], as_of)
            identity = (
                instrument.asset_type,
                instrument.market,
                instrument.exchange_mic,
                instrument.symbol,
            )
            if isinstance(instrument, FuturesInstrumentV2):
                identity += (instrument.contract_month,)
            if identity in seen:
                raise TargetValidationError(f"duplicate instrument: {identity!r}")
            seen.add(identity)
            weight = _decimal(item["weight"], "weight", pattern=_WEIGHT)
            quantity = (
                _decimal(item["quantity"], "quantity", positive=True)
                if "quantity" in item
                else None
            )
            if isinstance(instrument, FuturesInstrumentV2):
                if quantity is None or quantity != quantity.to_integral_value():
                    raise TargetValidationError(
                        "future quantity must be a positive integer contract count"
                    )
            targets.append(TargetV2(instrument, weight, quantity))

        # Fraction keeps aggregation exact even beyond Decimal's default context precision.
        if sum((Fraction(target.weight) for target in targets), Fraction(0)) > 1:
            raise TargetValidationError("sum of weights must be at most 1")
        return cls("2.0", strategy_id, as_of, currency, tuple(targets))

    def to_dict(self) -> dict[str, Any]:
        output: list[dict[str, Any]] = []
        for target in self.targets:
            instrument = target.instrument
            metadata: dict[str, Any] = {
                "asset_type": instrument.asset_type,
                "symbol": instrument.symbol,
                "market": instrument.market,
                "exchange_mic": instrument.exchange_mic,
                "currency": instrument.currency,
            }
            if isinstance(instrument, FuturesInstrumentV2):
                metadata.update(
                    contract_month=instrument.contract_month,
                    expiry_date=instrument.expiry_date.isoformat(),
                    multiplier=format(instrument.multiplier, "f"),
                    tick_size=format(instrument.tick_size, "f"),
                    roll_rule_id=instrument.roll_rule_id,
                    settlement_type=instrument.settlement_type,
                    margin_model_id=instrument.margin_model_id,
                )
            item: dict[str, Any] = {
                "instrument": metadata,
                "weight": format(target.weight, "f"),
            }
            if target.quantity is not None:
                item["quantity"] = format(target.quantity, "f")
            output.append(item)
        return {
            "schema_version": self.schema_version,
            "strategy_id": self.strategy_id,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "reporting_currency": self.reporting_currency,
            "targets": output,
        }


def _object(
    value: Any, required: set[str], label: str, *, optional: set[str] | None = None
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TargetValidationError(f"{label} must be an object")
    if set(value) - required - (optional or set()):
        raise TargetValidationError(f"unknown {label} field")
    if required - set(value):
        raise TargetValidationError(f"missing {label} field")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetValidationError(f"{label} must be a nonblank string")
    return value.strip()


def _match(value: Any, pattern: str | re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise TargetValidationError(f"invalid {label}")
    return value


def _decimal(
    value: Any,
    label: str,
    *,
    positive: bool = False,
    pattern: re.Pattern[str] = _DECIMAL,
) -> Decimal:
    text = _match(value, pattern, f"{label} decimal string")
    decimal = Decimal(text)
    if positive and decimal <= 0:
        raise TargetValidationError(f"{label} must be positive")
    return decimal


def _instrument(
    value: Any, as_of: datetime
) -> SecurityInstrumentV2 | FuturesInstrumentV2:
    if not isinstance(value, Mapping):
        raise TargetValidationError("instrument must be an object")
    asset_type = value.get("asset_type")
    if asset_type not in ("equity", "etf", "future"):
        raise TargetValidationError("unsupported asset_type")
    required = _COMMON | _FUTURE if asset_type == "future" else _COMMON
    item = _object(value, required, "instrument")
    common = {
        "asset_type": asset_type,
        "symbol": _text(item["symbol"], "symbol"),
        "market": _match(item["market"], r"[A-Z][A-Z0-9_-]*", "market"),
        "exchange_mic": _match(item["exchange_mic"], r"[A-Z0-9]{4}", "exchange_mic"),
        "currency": _match(item["currency"], r"[A-Z]{3}", "currency"),
    }
    if asset_type != "future":
        return SecurityInstrumentV2(**common)
    month = _match(item["contract_month"], r"[0-9]{6}", "contract_month")
    expiry = _match(item["expiry_date"], r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "expiry_date")
    try:
        date(int(month[:4]), int(month[4:]), 1)
        expiry_date = date.fromisoformat(expiry)
    except ValueError as exc:
        raise TargetValidationError(
            "invalid future contract month or expiry date"
        ) from exc
    if expiry_date <= as_of.date():
        raise TargetValidationError("expiry_date must be later than as_of UTC date")
    if item["settlement_type"] not in ("cash", "physical"):
        raise TargetValidationError("invalid settlement_type")
    return FuturesInstrumentV2(
        **common,
        contract_month=month,
        expiry_date=expiry_date,
        multiplier=_decimal(item["multiplier"], "multiplier", positive=True),
        tick_size=_decimal(item["tick_size"], "tick_size", positive=True),
        roll_rule_id=_text(item["roll_rule_id"], "roll_rule_id"),
        settlement_type=item["settlement_type"],
        margin_model_id=_text(item["margin_model_id"], "margin_model_id"),
    )
