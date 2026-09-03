from decimal import Decimal

import pytest

from packages.market_model import (
    AssetClass,
    Currency,
    Exchange,
    LotSizeError,
    Market,
    SymbolError,
    normalize_symbol,
    validate_quantity,
)


def test_normalizes_japanese_equity_with_jpy_tse_and_100_share_lot() -> None:
    instrument = normalize_symbol("7203.T")

    assert instrument.symbol == "7203.T"
    assert instrument.code == "7203"
    assert instrument.market is Market.JP
    assert instrument.exchange is Exchange.TSEJ
    assert instrument.currency is Currency.JPY
    assert instrument.asset_class is AssetClass.EQUITY
    assert instrument.lot_size == Decimal("100")


def test_normalizes_japanese_etf_with_one_unit_lot() -> None:
    instrument = normalize_symbol("1321.T")

    assert instrument.market is Market.JP
    assert instrument.exchange is Exchange.TSEJ
    assert instrument.currency is Currency.JPY
    assert instrument.asset_class is AssetClass.ETF
    assert instrument.lot_size == Decimal("1")


def test_us_symbol_does_not_use_japanese_market_defaults() -> None:
    instrument = normalize_symbol("AAPL.US")

    assert instrument.market is Market.US
    assert instrument.exchange is Exchange.SMART
    assert instrument.currency is Currency.USD
    assert instrument.lot_size == Decimal("1")


def test_rejects_malformed_or_unknown_market_suffix() -> None:
    with pytest.raises(SymbolError):
        normalize_symbol("7203")

    with pytest.raises(SymbolError):
        normalize_symbol("7203.XJP")


def test_validates_quantity_against_instrument_lot_size() -> None:
    instrument = normalize_symbol("7203.T")
    validate_quantity(instrument, Decimal("200"))

    with pytest.raises(LotSizeError, match="100"):
        validate_quantity(instrument, Decimal("99"))


def test_rejects_non_positive_quantity() -> None:
    with pytest.raises(LotSizeError, match="positive"):
        validate_quantity(normalize_symbol("1321.T"), Decimal("0"))
