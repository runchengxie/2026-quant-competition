# Derived from quant-platform 28a32ba707ad72d1eb68cde5075663e1b3819ac7.
# Modified for the competition namespace/identity; licensed under Apache-2.0.
# See accounting/ORIGIN.json and LICENSE-APACHE-2.0.txt for provenance and terms.
"""Synthetic USD ledger fixtures; no market data or strategy assumptions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from platform_compare.accounting.contracts import ArtifactRef, ResearchClock

from platform_compare.accounting.usd_ledger_models import (
    USDInstrument,
    USDPriceObservation,
    USDRebalanceDecision,
    USDReplayConfig,
    USDReplayRequest,
)

D = Decimal
REF = ArtifactRef("synthetic-marks", "a" * 64)


def at(day=1, hour=0):
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def instrument(name="A", currency="USD", lot=1):
    return USDInstrument(name, "etf", currency, lot, "synthetic-session.v1")


def price(name="A", day=1, value="10", hour=0, **overrides):
    fields = {
        "instrument_id": name,
        "price_at": at(day, hour),
        "available_at": at(day, hour),
        "price": D(value),
        "unit": "currency_per_share",
        "source_ref": REF,
        "availability_basis": "verified",
        "session_policy_id": "synthetic-session.v1",
        "execution_eligible": True,
    }
    return USDPriceObservation(**(fields | overrides))


def config(**overrides):
    fields = {
        "initial_cash": D("100"),
        "sizing_mode": "fractional",
        "commission_bps": D("0"),
        "slippage_bps": D("0"),
        "fx_cost_bps": D("0"),
        "max_price_age": timedelta(days=5),
        "max_fx_age": timedelta(days=5),
        "fx_pairs": {},
    }
    return USDReplayConfig(**(fields | overrides))


def decision(day=1, weights=None, times=None):
    times = times if times is not None else {"A": at(day, 1)}
    start, end = (min(times.values()), max(times.values())) if times else (at(day, 1), at(day, 1))
    clock = ResearchClock(
        "UTC",
        at(day),
        at(day),
        at(day),
        at(5),
        "synthetic-next-mark.v1",
        "synthetic.v1",
        start,
        start,
        end,
    )
    return USDRebalanceDecision(
        f"d{day}", clock, {"A": D("0.5")} if weights is None else weights, times
    )


def request(**overrides):
    fields = {
        "instruments": (instrument(),),
        "prices": (price(), price(hour=1)),
        "fx": (),
        "decisions": (decision(),),
        "valuation_times": (at(1), at(2), at(3)),
        "config": config(),
    }
    return USDReplayRequest(**(fields | overrides))
