# Derived from quant-platform 28a32ba707ad72d1eb68cde5075663e1b3819ac7.
# Modified for the competition namespace/identity; licensed under Apache-2.0.
# See accounting/ORIGIN.json and LICENSE-APACHE-2.0.txt for provenance and terms.
"""Fail-closed validation and backward causal mark selection."""

import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Any, cast

from platform_compare.accounting.contracts import ArtifactRef, ResearchClock

from .usd_ledger_models import (
    USDFXObservation,
    USDModeledExecutionPrice,
    USDPriceObservation,
    USDReplayConfig,
    USDReplayRequest,
    USDValidationError,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise USDValidationError(message)


def decimal_value(value: Any, field: str, *, positive: bool = False) -> Decimal:
    require(isinstance(value, Decimal), f"{field} must be Decimal")
    require(value.is_finite(), f"{field} must be finite")
    require(value > 0 if positive else value >= 0, f"{field} out of range")
    return value


def utc_time(value: Any) -> datetime:
    require(isinstance(value, datetime), "timestamp must be datetime")
    require(value.tzinfo is not None and value.utcoffset() == timedelta(0), "timestamp must be UTC")
    return value


def _text(value: Any) -> None:
    require(isinstance(value, str) and bool(value.strip()), "identifier must be nonblank text")


def _currency(value: Any) -> None:
    require(
        isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value) is not None,
        "currency must be three uppercase letters",
    )


def validate_usd_config(config: USDReplayConfig) -> None:
    require(isinstance(config, USDReplayConfig), "config must be USDReplayConfig")
    decimal_value(config.initial_cash, "initial_cash", positive=True)
    costs = [
        decimal_value(getattr(config, f), f)
        for f in ("commission_bps", "slippage_bps", "fx_cost_bps")
    ]
    with localcontext() as ctx:
        ctx.prec = 50
        require(sum(costs) < 10000, "combined costs must be below 10000 bps")
    require(config.sizing_mode in ("fractional", "integral"), "unsupported sizing mode")
    require(config.return_basis == "price", "only price NAV is supported")
    require(type(config.allow_assumed_availability) is bool, "availability flag must be bool")
    require(type(config.allow_modeled_execution_prices) is bool, "modeled price flag must be bool")
    for age in (config.max_price_age, config.max_fx_age):
        require(isinstance(age, timedelta) and age > timedelta(0), "maximum age must be positive")
    require(isinstance(config.fx_pairs, Mapping), "fx_pairs must be mapping")
    for currency, pair in config.fx_pairs.items():
        _currency(currency)
        require(
            currency != "USD" and isinstance(pair, tuple) and len(pair) == 2,
            "FX mapping must specify one explicit pair",
        )
        require(
            pair in ((currency, "USD"), ("USD", currency)), "FX pair must be direct or inverse USD"
        )


def _validate_instruments(request: USDReplayRequest) -> dict:
    from .usd_ledger_models import USDInstrument

    instruments = {}
    for item in request.instruments:
        require(isinstance(item, USDInstrument), "invalid instrument record")
        _text(item.instrument_id)
        _text(item.session_policy_id)
        _currency(item.currency)
        require(item.asset_type in ("equity", "etf"), "unsupported asset type")
        require(
            type(item.lot_size) is int and item.lot_size > 0, "lot_size must be positive integer"
        )
        require(item.instrument_id not in instruments, "duplicate instrument ID")
        require(
            item.currency == "USD" or item.currency in request.config.fx_pairs,
            "explicit FX pair required",
        )
        instruments[item.instrument_id] = item
    return instruments


def _validate_observation(row: Any, config: USDReplayConfig) -> None:
    utc_time(row.price_at)
    utc_time(row.available_at)
    require(row.price_at <= row.available_at, "availability precedes observation")
    require(
        row.availability_basis in ("verified", "assumed_date_lag", "assumed_market_session"),
        "invalid availability basis",
    )
    if row.availability_basis == "assumed_date_lag":
        require(config.allow_assumed_availability, "assumed availability not enabled")
    elif row.availability_basis == "assumed_market_session":
        require(
            isinstance(row, USDFXObservation)
            and config.allow_assumed_availability
            and config.allow_modeled_execution_prices,
            "assumed market-session availability requires both explicit opt-ins",
        )
    require(isinstance(row.source_ref, ArtifactRef), "immutable source reference required")
    try:
        ArtifactRef.from_mapping(row.source_ref.to_mapping())
    except ValueError as exc:
        raise USDValidationError("invalid source reference") from exc


def _validate_series(request: USDReplayRequest, instruments: dict) -> None:
    seen, sources = set(), {}
    for row in (*request.prices, *request.fx):
        require(isinstance(row, (USDPriceObservation, USDFXObservation)), "invalid observation")
        _validate_observation(row, request.config)
        if isinstance(row, USDPriceObservation):
            require(row.instrument_id in instruments, "unknown price instrument")
            require(row.unit == "currency_per_share", "invalid price unit")
            require(
                row.session_policy_id == instruments[row.instrument_id].session_policy_id,
                "session policy mismatch",
            )
            require(type(row.execution_eligible) is bool, "execution_eligible must be bool")
            decimal_value(row.price, "price", positive=True)
            series = ("price", row.instrument_id)
        else:
            _currency(row.base_currency)
            _currency(row.quote_currency)
            require(row.base_currency != row.quote_currency, "invalid FX pair")
            require(row.unit == "quote_per_base", "invalid FX unit")
            decimal_value(row.rate, "FX rate", positive=True)
            series = ("fx", row.base_currency, row.quote_currency)
        key = (*series, row.price_at)
        require(key not in seen, "duplicate series timestamp")
        seen.add(key)
        ref = (row.source_ref.artifact_id, row.source_ref.sha256)
        require(series not in sources or sources[series] == ref, "source series replacement")
        sources[series] = ref


def _validate_modeled_execution_prices(request: USDReplayRequest, instruments: dict) -> None:
    rows = request.modeled_execution_prices
    require(isinstance(rows, tuple), "modeled_execution_prices must be tuple")
    require(
        not rows or request.config.allow_modeled_execution_prices,
        "modeled execution prices require explicit opt-in",
    )
    seen = set()
    scheduled = {
        (instrument_id, timestamp)
        for decision in request.decisions
        for instrument_id, timestamp in decision.execution_times.items()
    }
    for row in rows:
        require(isinstance(row, USDModeledExecutionPrice), "invalid modeled execution price")
        _text(row.instrument_id)
        require(row.instrument_id in instruments, "unknown modeled price instrument")
        require(type(row.session_date) is date, "modeled session_date must be date")
        utc_time(row.scheduled_open_at)
        require(
            (row.instrument_id, row.scheduled_open_at) in scheduled,
            "modeled price does not match a scheduled execution",
        )
        require(row.unit == "currency_per_share", "invalid modeled price unit")
        decimal_value(row.reference_price, "modeled reference price", positive=True)
        require(isinstance(row.source_ref, ArtifactRef), "immutable source reference required")
        try:
            ArtifactRef.from_mapping(row.source_ref.to_mapping())
        except ValueError as exc:
            raise USDValidationError("invalid source reference") from exc
        require(
            row.session_policy_id == instruments[row.instrument_id].session_policy_id,
            "modeled session policy mismatch",
        )
        _text(row.model_id)
        key = (row.instrument_id, row.scheduled_open_at)
        require(key not in seen, "duplicate modeled instrument and scheduled open")
        seen.add(key)


def _validate_decisions(request: USDReplayRequest, instruments: dict) -> None:
    from .usd_ledger_models import USDRebalanceDecision

    previous_end, previous_decision, ids = None, None, set()
    for decision in request.decisions:
        require(isinstance(decision, USDRebalanceDecision), "invalid decision record")
        _text(decision.decision_id)
        require(decision.decision_id not in ids, "duplicate decision ID")
        ids.add(decision.decision_id)
        require(isinstance(decision.clock, ResearchClock), "ResearchClock required")
        try:
            clock = ResearchClock.from_mapping(decision.clock.to_mapping())
        except ValueError as exc:
            raise USDValidationError("invalid research clock") from exc
        require(clock.timezone == "UTC", "clock timezone must be UTC")
        for key, value in vars(clock).items():
            if key.endswith("_at") and value is not None:
                utc_time(value)
        require(isinstance(decision.weights, Mapping), "weights must be mapping")
        require(set(decision.weights) <= set(instruments), "unknown target instrument")
        with localcontext() as ctx:
            ctx.prec = 50
            require(
                sum(decimal_value(w, "weight") for w in decision.weights.values()) <= 1,
                "weights exceed one",
            )
        require(
            isinstance(decision.execution_times, Mapping)
            and set(decision.execution_times) == set(instruments),
            "execution universe mismatch",
        )
        require(
            clock.earliest_order_at is not None
            and clock.execution_window_start_at is not None
            and clock.execution_window_end_at is not None,
            "explicit execution bounds required",
        )
        earliest = cast(datetime, clock.earliest_order_at)
        start = cast(datetime, clock.execution_window_start_at)
        end = cast(datetime, clock.execution_window_end_at)
        require(
            previous_decision is None or clock.decision_at > previous_decision,
            "decision times must increase",
        )
        require(previous_end is None or clock.decision_at > previous_end, "overlapping decisions")
        for time in decision.execution_times.values():
            utc_time(time)
            require(
                time > clock.decision_at and time >= earliest and start <= time <= end,
                "execution outside causal bounds",
            )
        require(
            request.valuation_times[0] <= clock.decision_at and request.valuation_times[-1] >= end,
            "valuation grid too short",
        )
        previous_decision, previous_end = clock.decision_at, clock.execution_window_end_at


def validate_usd_request(request: USDReplayRequest) -> None:
    require(isinstance(request, USDReplayRequest), "USDReplayRequest required")
    validate_usd_config(request.config)
    for field in ("instruments", "prices", "fx", "decisions", "valuation_times"):
        require(isinstance(getattr(request, field), tuple), f"{field} must be tuple")
    require(bool(request.valuation_times), "nonempty valuation grid required")
    times = [utc_time(t) for t in request.valuation_times]
    require(times == sorted(set(times)), "valuation times must be sorted and unique")
    instruments = _validate_instruments(request)
    require(
        all(isinstance(p, USDPriceObservation) for p in request.prices), "price records required"
    )
    require(all(isinstance(f, USDFXObservation) for f in request.fx), "FX records required")
    _validate_series(request, instruments)
    _validate_decisions(request, instruments)
    _validate_modeled_execution_prices(request, instruments)


def _asof(rows: list[Any], at: datetime, age: timedelta) -> Any:
    utc_time(at)
    eligible = [r for r in rows if r.price_at <= at and r.available_at <= at]
    require(bool(eligible), "missing available observation")
    row = max(eligible, key=lambda r: r.price_at)
    require(at - row.price_at <= age, "stale observation")
    require(sum(r.price_at == row.price_at for r in eligible) == 1, "ambiguous observation")
    return row


def select_usd_price(
    request: USDReplayRequest, instrument_id: str, at: datetime, *, execution: bool = False
) -> USDPriceObservation:
    row = _asof(
        [r for r in request.prices if r.instrument_id == instrument_id],
        at,
        request.config.max_price_age,
    )
    _validate_observation(row, request.config)
    decimal_value(row.price, "price", positive=True)
    if execution:
        require(
            row.price_at == at
            and row.execution_eligible is True
            and row.availability_basis == "verified",
            "ineligible execution mark",
        )
    return row


def select_usd_modeled_execution_price(
    request: USDReplayRequest, instrument_id: str, at: datetime
) -> USDModeledExecutionPrice:
    require(
        request.config.allow_modeled_execution_prices,
        "modeled execution prices require explicit opt-in",
    )
    utc_time(at)
    rows = [
        row
        for row in request.modeled_execution_prices
        if row.instrument_id == instrument_id and row.scheduled_open_at == at
    ]
    require(len(rows) == 1, "missing or ambiguous exact modeled execution reference")
    row = rows[0]
    _text(row.model_id)
    decimal_value(row.reference_price, "modeled reference price", positive=True)
    return row


def select_usd_fx(
    request: USDReplayRequest, currency: str, at: datetime
) -> tuple[Decimal, USDFXObservation | None]:
    utc_time(at)
    if currency == "USD":
        return Decimal(1), None
    require(currency in request.config.fx_pairs, "explicit FX pair required")
    pair = request.config.fx_pairs[currency]
    require(pair in ((currency, "USD"), ("USD", currency)), "invalid selected FX pair")
    row = _asof(
        [r for r in request.fx if (r.base_currency, r.quote_currency) == pair],
        at,
        request.config.max_fx_age,
    )
    _validate_observation(row, request.config)
    decimal_value(row.rate, "FX rate", positive=True)
    with localcontext() as ctx:
        ctx.prec = 50
        return (row.rate if pair[0] == currency else Decimal(1) / row.rate), row
