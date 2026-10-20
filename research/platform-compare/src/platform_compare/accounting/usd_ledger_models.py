"""Explicit inputs for diagnostic USD cash-equity price accounting."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from platform_compare.accounting.contracts import ArtifactRef, ResearchClock


class USDValidationError(ValueError):
    """Invalid, unavailable or unsupported USD ledger input."""


@dataclass(frozen=True)
class USDInstrument:
    instrument_id: str
    asset_type: str
    currency: str
    lot_size: int
    session_policy_id: str


@dataclass(frozen=True)
class USDPriceObservation:
    instrument_id: str
    price_at: datetime
    available_at: datetime
    price: Decimal
    unit: str
    source_ref: ArtifactRef
    availability_basis: str
    session_policy_id: str
    execution_eligible: bool


@dataclass(frozen=True)
class USDModeledExecutionPrice:
    instrument_id: str
    session_date: date
    scheduled_open_at: datetime
    reference_price: Decimal
    unit: str
    source_ref: ArtifactRef
    session_policy_id: str
    model_id: str


@dataclass(frozen=True)
class USDFXObservation:
    base_currency: str
    quote_currency: str
    price_at: datetime
    available_at: datetime
    rate: Decimal
    unit: str
    source_ref: ArtifactRef
    availability_basis: str


@dataclass(frozen=True)
class USDRebalanceDecision:
    decision_id: str
    clock: ResearchClock
    weights: Mapping[str, Decimal]
    execution_times: Mapping[str, datetime]


@dataclass(frozen=True)
class USDReplayConfig:
    initial_cash: Decimal
    sizing_mode: str
    commission_bps: Decimal
    slippage_bps: Decimal
    fx_cost_bps: Decimal
    max_price_age: timedelta
    max_fx_age: timedelta
    fx_pairs: Mapping[str, tuple[str, str]]
    allow_assumed_availability: bool = False
    return_basis: str = "price"
    allow_modeled_execution_prices: bool = False


@dataclass(frozen=True)
class USDReplayRequest:
    instruments: tuple[USDInstrument, ...]
    prices: tuple[USDPriceObservation, ...]
    fx: tuple[USDFXObservation, ...]
    decisions: tuple[USDRebalanceDecision, ...]
    valuation_times: tuple[datetime, ...]
    config: USDReplayConfig
    modeled_execution_prices: tuple[USDModeledExecutionPrice, ...] = ()


@dataclass(frozen=True)
class USDReplayResult:
    daily: pd.DataFrame
    holdings: pd.DataFrame
    transactions: pd.DataFrame
    targets: pd.DataFrame
    decision_clocks: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
