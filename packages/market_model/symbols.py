"""Normalize competition symbols without depending on a broker SDK."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re


class Market(str, Enum):
    JP = "JP"
    US = "US"


class Exchange(str, Enum):
    TSEJ = "TSEJ"
    SMART = "SMART"


class Currency(str, Enum):
    JPY = "JPY"
    USD = "USD"


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"


class SymbolError(ValueError):
    """Raised when a canonical competition symbol cannot be normalized."""


class LotSizeError(ValueError):
    """Raised when an order quantity is not valid for its instrument."""


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    """Broker-neutral instrument details needed before an order is built."""

    symbol: str
    code: str
    market: Market
    exchange: Exchange
    currency: Currency
    asset_class: AssetClass
    lot_size: Decimal


_SYMBOL_RE = re.compile(r"^(?P<code>[A-Z0-9]{1,12})\.(?P<suffix>[A-Z]+)$")

# These are the Japanese ETF symbols used by the initial Nira exploration.  A
# caller can still explicitly pass ``asset_class=ETF`` for another ETF while
# its exchange-specific metadata is added later.
_JP_UNIT_LOT_ETFS = frozenset({"1306", "1320", "1321", "1348", "2558", "2568", "2569"})


def normalize_symbol(
    symbol: str, *, asset_class: AssetClass | str | None = None
) -> InstrumentSpec:
    """Return canonical market metadata for a supported competition symbol.

    The first version deliberately supports the symbols required by the
    execution boundary: Japanese ``.T`` symbols and US ``.US`` symbols.
    Broker-specific contract fields are added by the IBKR adapter later.
    """

    if not isinstance(symbol, str):
        raise SymbolError("symbol must be a string")
    canonical = symbol.strip().upper()
    match = _SYMBOL_RE.fullmatch(canonical)
    if match is None:
        raise SymbolError(f"unsupported symbol format: {symbol!r}")

    code = match.group("code")
    suffix = match.group("suffix")
    requested_class = _parse_asset_class(asset_class) if asset_class is not None else None

    if suffix == "T":
        inferred_class = (
            AssetClass.ETF if code in _JP_UNIT_LOT_ETFS else AssetClass.EQUITY
        )
        resolved_class = requested_class or inferred_class
        if resolved_class not in (AssetClass.EQUITY, AssetClass.ETF):
            raise SymbolError(f"unsupported Japanese asset class: {resolved_class.value}")
        return InstrumentSpec(
            symbol=canonical,
            code=code,
            market=Market.JP,
            exchange=Exchange.TSEJ,
            currency=Currency.JPY,
            asset_class=resolved_class,
            lot_size=Decimal("1") if resolved_class is AssetClass.ETF else Decimal("100"),
        )

    if suffix == "US":
        resolved_class = requested_class or AssetClass.EQUITY
        if resolved_class not in (AssetClass.EQUITY, AssetClass.ETF):
            raise SymbolError(f"unsupported US asset class: {resolved_class.value}")
        return InstrumentSpec(
            symbol=canonical,
            code=code,
            market=Market.US,
            exchange=Exchange.SMART,
            currency=Currency.USD,
            asset_class=resolved_class,
            lot_size=Decimal("1"),
        )

    raise SymbolError(f"unsupported market suffix: .{suffix}")


def validate_quantity(instrument: InstrumentSpec, quantity: Decimal | int | str) -> Decimal:
    """Validate and return a positive quantity aligned to the lot size."""

    value = _as_decimal(quantity, field="quantity")
    if value <= 0:
        raise LotSizeError("quantity must be positive")
    if value % instrument.lot_size != 0:
        raise LotSizeError(
            f"quantity {value} is not a multiple of lot size {instrument.lot_size}"
        )
    return value


def _parse_asset_class(value: AssetClass | str) -> AssetClass:
    try:
        return value if isinstance(value, AssetClass) else AssetClass(value.lower())
    except (AttributeError, ValueError) as exc:
        raise SymbolError(f"unsupported asset class: {value!r}") from exc


def _as_decimal(value: Decimal | int | str, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise LotSizeError(f"{field} must be a decimal value")
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LotSizeError(f"{field} must be a decimal value") from exc
    if not decimal.is_finite():
        raise LotSizeError(f"{field} must be finite")
    return decimal
