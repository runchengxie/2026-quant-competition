from decimal import Decimal

from packages.market_model import Currency, Exchange, Market, normalize_symbol


def test_normalizes_hong_kong_equity_with_hkd_sehk_and_baseline_lot():
    instrument = normalize_symbol("0700.HK")

    assert instrument.market is Market.HK
    assert instrument.exchange is Exchange.SEHK
    assert instrument.currency is Currency.HKD
    assert instrument.lot_size == Decimal("100")
