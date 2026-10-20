"""Strategy-specific adapter to the public modeled USD price ledger."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

import pandas as pd
from exchange_calendars import get_calendar
from platform_compare.accounting.contracts import ArtifactRef, ResearchClock

from platform_compare.accounting.usd_ledger_models import (
    USDFXObservation,
    USDInstrument,
    USDModeledExecutionPrice,
    USDPriceObservation,
    USDRebalanceDecision,
    USDReplayConfig,
    USDReplayRequest,
)

from .calendar import (
    CALENDAR_PACKAGE,
    CALENDAR_PACKAGE_VERSION,
    MARKET_CALENDARS,
    CalendarSet,
    _scheduled_session,
    derive_signal_clock,
    first_open_after,
)
from .loader import ASSET_FILES, FX_FILES, NextOpenInputs

CUTOFF_DATE = date(2026, 10, 1)
MODEL_ID = "ibkr-daily-first-rth-trade-open.v1"
TIMING_POLICY_ID = "global-etf-next-open-after-global-signal-close.v1"
SESSION_POLICY_PREFIX = "global-etf-next-open-calendar.v1"

ASSET_METADATA: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "US_SPY": MappingProxyType(
            {"market": "US", "currency": "USD", "symbol": "SPY", "exchange": "ARCA"}
        ),
        "HK_2800": MappingProxyType(
            {"market": "HK", "currency": "HKD", "symbol": "2800", "exchange": "SEHK"}
        ),
        "UK_ISF": MappingProxyType(
            {"market": "UK", "currency": "GBP", "symbol": "ISF", "exchange": "LSEETF"}
        ),
        "AU_STW": MappingProxyType(
            {"market": "AU", "currency": "AUD", "symbol": "STW", "exchange": "ASX"}
        ),
        "SG_ES3": MappingProxyType(
            {"market": "SG", "currency": "SGD", "symbol": "ES3", "exchange": "SGX"}
        ),
    }
)
FX_FILE_FOR_CURRENCY = {
    "HKD": ("USD", "HKD", "USDHKD"),
    "GBP": ("GBP", "USD", "GBPUSD"),
    "AUD": ("AUD", "USD", "AUDUSD"),
    "SGD": ("USD", "SGD", "USDSGD"),
}


@dataclass(frozen=True, slots=True)
class CostScenario:
    scenario_id: str
    commission_bps: Decimal
    slippage_bps: Decimal
    fx_cost_bps: Decimal
    label: str


def _scenario_id(commission: int, slippage: int, fx: int) -> str:
    return f"commission-{commission}_slippage-{slippage}_fx-{fx}"


def build_cost_scenarios() -> tuple[CostScenario, ...]:
    scenarios: list[CostScenario] = []
    for commission in (0, 5, 10):
        for slippage in (0, 5, 10, 20):
            for fx in (0, 5, 10):
                is_reference = (commission, slippage, fx) == (5, 5, 0)
                label = (
                    "Reference case; zero FX cost is an optimistic lower bound"
                    if is_reference
                    else "Cost sensitivity scenario"
                )
                scenarios.append(
                    CostScenario(
                        _scenario_id(commission, slippage, fx),
                        Decimal(commission),
                        Decimal(slippage),
                        Decimal(fx),
                        label,
                    )
                )
    return tuple(scenarios)


def _calendar_set(calendars: CalendarSet | None) -> CalendarSet:
    if calendars is not None:
        return calendars
    return MappingProxyType(
        {
            market: get_calendar(calendar_name)
            for market, calendar_name in MARKET_CALENDARS.items()
        }
    )


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite {field}")
    return result


def _file_ref(inputs: NextOpenInputs, filename: str) -> ArtifactRef:
    digest = inputs.input_hashes.get(filename)
    if digest is None:
        raise ValueError(f"missing input hash for {filename}")
    return ArtifactRef(f"ibkr-daily:{filename}", digest)


def _date_column(frame: pd.DataFrame) -> tuple[date, ...]:
    values = tuple(frame["date"])
    result = []
    for value in values:
        if isinstance(value, pd.Timestamp):
            value = value.date()
        if type(value) is not date:
            raise ValueError("input date must be a plain local session date")
        result.append(value)
    return tuple(result)


def _market_source_dates(inputs: NextOpenInputs, signal_date: date) -> dict[str, date]:
    result: dict[str, date] = {}
    for instrument_id, metadata in ASSET_METADATA.items():
        eligible = [
            d for d in _date_column(inputs.assets[instrument_id]) if d <= signal_date
        ]
        if not eligible:
            raise ValueError(
                f"no source session at or before signal date for {instrument_id}"
            )
        result[metadata["market"]] = max(eligible)
    return result


def _weights(rebalance: Mapping[str, object]) -> dict[str, Decimal]:
    targets = rebalance.get("targets")
    if not isinstance(targets, list):
        raise ValueError("target schedule has an invalid targets list")
    weights = dict.fromkeys(ASSET_METADATA, Decimal(0))
    seen = set()
    for target in targets:
        if not isinstance(target, Mapping):
            raise ValueError("target schedule row must be an object")
        instrument = target.get("instrument_id")
        if instrument not in ASSET_METADATA or instrument in seen:
            raise ValueError(
                "target schedule contains an unsupported or duplicate asset"
            )
        seen.add(instrument)
        weight = _decimal(target.get("weight"), "target weight")
        if weight < 0:
            raise ValueError("target weight cannot be negative")
        weights[str(instrument)] = weight
    if sum(weights.values(), Decimal(0)) > 1:
        raise ValueError("target weights exceed one")
    return weights


def _validate_adapter_inputs(
    inputs: NextOpenInputs, scenario: CostScenario, initial_cash: Decimal
) -> None:
    if set(inputs.assets) != set(ASSET_METADATA):
        raise ValueError("input asset universe must match the five configured ETFs")
    if set(inputs.fx) != set(FX_FILES):
        raise ValueError(
            "input FX universe must contain the five configured currency pairs"
        )
    if inputs.dataset_manifest.get("execution_eligible") is not False:
        raise ValueError("dataset is not diagnostic-only")
    if (
        inputs.dataset_manifest.get("analysis_cutoff_local_date")
        != CUTOFF_DATE.isoformat()
    ):
        raise ValueError("input dataset cutoff must be 2026-10-01")
    if not isinstance(scenario, CostScenario):
        raise ValueError("scenario must be a CostScenario")
    scenario_rates = (
        scenario.commission_bps,
        scenario.slippage_bps,
        scenario.fx_cost_bps,
    )
    if any(
        not isinstance(value, Decimal) or not value.is_finite() or value < 0
        for value in scenario_rates
    ):
        raise ValueError("scenario costs must be finite nonnegative Decimals")
    if (
        not isinstance(initial_cash, Decimal)
        or not initial_cash.is_finite()
        or initial_cash <= 0
    ):
        raise ValueError("initial_cash must be a positive finite Decimal")


def _parse_rebalances(
    schedule: Mapping[str, object],
) -> list[tuple[date, dict[str, Decimal]]]:
    rebalances = schedule.get("rebalances")
    if not isinstance(rebalances, list) or not rebalances:
        raise ValueError("target schedule has no decisions")
    parsed: list[tuple[date, dict[str, Decimal]]] = []
    for rebalance in rebalances:
        if not isinstance(rebalance, Mapping):
            raise ValueError("target schedule decision must be an object")
        try:
            signal_date = date.fromisoformat(str(rebalance["signal_as_of_date"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("target schedule has an invalid signal date") from exc
        if signal_date > CUTOFF_DATE:
            raise ValueError("target schedule contains a signal after the cutoff")
        parsed.append((signal_date, _weights(rebalance)))
    parsed.sort(key=lambda row: row[0])
    if len({row[0] for row in parsed}) != len(parsed):
        raise ValueError("target schedule contains duplicate signal dates")
    return parsed


def _make_instruments() -> tuple[USDInstrument, ...]:
    return tuple(
        USDInstrument(
            instrument_id,
            "etf",
            metadata["currency"],
            1,
            f"{SESSION_POLICY_PREFIX}:{metadata['market']}:{MARKET_CALENDARS[metadata['market']]}",
        )
        for instrument_id, metadata in ASSET_METADATA.items()
    )


def _rows_by_date(frame: pd.DataFrame) -> dict[date, dict[str, object]]:
    return dict(zip(_date_column(frame), frame.to_dict("records"), strict=True))


def _input_indexes(inputs: NextOpenInputs):
    records = {
        instrument_id: _rows_by_date(inputs.assets[instrument_id])
        for instrument_id in ASSET_METADATA
    }
    fx_records = {pair: _rows_by_date(frame) for pair, frame in inputs.fx.items()}
    fx_refs = {pair: _file_ref(inputs, filename) for pair, filename in FX_FILES.items()}
    return records, fx_records, fx_refs


def _make_close_and_fx_rows(
    inputs: NextOpenInputs,
    instruments: tuple[USDInstrument, ...],
    records: Mapping[str, Mapping[date, Mapping[str, object]]],
    fx_records: Mapping[str, Mapping[date, Mapping[str, object]]],
    fx_refs: Mapping[str, ArtifactRef],
    *,
    start_date: date,
    calendars: CalendarSet,
) -> tuple[list[USDPriceObservation], list[USDFXObservation], set[datetime]]:
    close_rows: list[USDPriceObservation] = []
    fx_rows: list[USDFXObservation] = []
    times: set[datetime] = set()
    policy_ids = {row.instrument_id: row.session_policy_id for row in instruments}
    for instrument_id, metadata in ASSET_METADATA.items():
        market = metadata["market"]
        currency = metadata["currency"]
        policy_id = policy_ids[instrument_id]
        ref = _file_ref(inputs, ASSET_FILES[instrument_id])
        for session_date, record in records[instrument_id].items():
            if session_date < start_date or session_date > CUTOFF_DATE:
                continue
            scheduled = _scheduled_session(market, session_date, calendars)
            price = _decimal(record["close"], f"{instrument_id} close")
            close_rows.append(
                USDPriceObservation(
                    instrument_id,
                    scheduled.scheduled_close_at,
                    scheduled.scheduled_close_at,
                    price,
                    "currency_per_share",
                    ref,
                    "assumed_date_lag",
                    policy_id,
                    False,
                )
            )
            times.add(scheduled.scheduled_close_at)
            if currency == "USD":
                continue
            base, quote, pair = FX_FILE_FOR_CURRENCY[currency]
            fx_record = fx_records[pair].get(session_date)
            if fx_record is None:
                raise ValueError(
                    f"missing same-session FX midpoint open for {currency} {session_date}"
                )
            rate = _decimal(fx_record["open"], f"{currency} FX open")
            fx_rows.append(
                USDFXObservation(
                    base,
                    quote,
                    scheduled.scheduled_open_at,
                    scheduled.scheduled_open_at,
                    rate,
                    "quote_per_base",
                    fx_refs[pair],
                    "assumed_market_session",
                )
            )
            times.add(scheduled.scheduled_open_at)
    return close_rows, fx_rows, times


def _make_decisions_and_open_rows(
    inputs: NextOpenInputs,
    parsed_rebalances: list[tuple[date, dict[str, Decimal]]],
    instruments: tuple[USDInstrument, ...],
    records: Mapping[str, Mapping[date, Mapping[str, object]]],
    calendars: CalendarSet,
) -> tuple[list[USDRebalanceDecision], list[USDModeledExecutionPrice], set[datetime]]:
    decisions: list[USDRebalanceDecision] = []
    open_rows: list[USDModeledExecutionPrice] = []
    times: set[datetime] = set()
    decision_ids = set()
    policy_ids = {row.instrument_id: row.session_policy_id for row in instruments}
    for signal_date, weights in parsed_rebalances:
        source_sessions = _market_source_dates(inputs, signal_date)
        decision_at = derive_signal_clock(signal_date, source_sessions, calendars)
        execution_times = {}
        for instrument_id, metadata in ASSET_METADATA.items():
            execution = first_open_after(
                metadata["market"],
                decision_at,
                tuple(records[instrument_id]),
                calendars,
            )
            record = records[instrument_id].get(execution.session_date)
            if record is None:
                raise ValueError(f"missing modeled open source row for {instrument_id}")
            open_rows.append(
                USDModeledExecutionPrice(
                    instrument_id,
                    execution.session_date,
                    execution.scheduled_open_at,
                    _decimal(record["open"], f"{instrument_id} modeled open"),
                    "currency_per_share",
                    _file_ref(inputs, ASSET_FILES[instrument_id]),
                    policy_ids[instrument_id],
                    MODEL_ID,
                )
            )
            execution_times[instrument_id] = execution.scheduled_open_at
            times.add(execution.scheduled_open_at)
        window_start = min(execution_times.values())
        window_end = max(execution_times.values())
        decision_id = f"global-etf-next-open-{signal_date.isoformat()}"
        if decision_id in decision_ids:
            raise ValueError("duplicate generated decision ID")
        decision_ids.add(decision_id)
        clock = ResearchClock(
            "UTC",
            decision_at,
            decision_at,
            decision_at,
            window_end,
            TIMING_POLICY_ID,
            f"{CALENDAR_PACKAGE}=={CALENDAR_PACKAGE_VERSION}:"
            + "+".join(MARKET_CALENDARS.values()),
            window_start,
            window_start,
            window_end,
        )
        decisions.append(
            USDRebalanceDecision(decision_id, clock, weights, execution_times)
        )
        times.add(decision_at)
    return decisions, open_rows, times


def build_replay_request(
    inputs: NextOpenInputs,
    scenario: CostScenario,
    *,
    initial_cash: Decimal,
    max_price_age: timedelta,
    max_fx_age: timedelta,
    calendars: CalendarSet | None = None,
) -> USDReplayRequest:
    """Build immutable platform ledger inputs from one frozen target schedule."""
    _validate_adapter_inputs(inputs, scenario, initial_cash)
    calendar_map = _calendar_set(calendars)
    parsed_rebalances = _parse_rebalances(inputs.target_schedule)
    instruments = _make_instruments()
    records, fx_records, fx_refs = _input_indexes(inputs)
    start_date = parsed_rebalances[0][0] - timedelta(days=max_price_age.days)
    close_rows, fx_rows, valuation_times = _make_close_and_fx_rows(
        inputs,
        instruments,
        records,
        fx_records,
        fx_refs,
        start_date=start_date,
        calendars=calendar_map,
    )
    decisions, open_rows, event_times = _make_decisions_and_open_rows(
        inputs, parsed_rebalances, instruments, records, calendar_map
    )
    valuation_times.update(event_times)
    fx_pairs = {
        currency: (base, quote)
        for currency, (base, quote, _) in FX_FILE_FOR_CURRENCY.items()
    }
    if not close_rows or not open_rows:
        raise ValueError("no close or modeled open observations available")
    return USDReplayRequest(
        instruments,
        tuple(close_rows),
        tuple(fx_rows),
        tuple(decisions),
        tuple(sorted(valuation_times)),
        USDReplayConfig(
            initial_cash,
            "fractional",
            scenario.commission_bps,
            scenario.slippage_bps,
            scenario.fx_cost_bps,
            max_price_age,
            max_fx_age,
            fx_pairs,
            allow_assumed_availability=True,
            allow_modeled_execution_prices=True,
        ),
        tuple(open_rows),
    )


__all__ = [
    "ASSET_METADATA",
    "CostScenario",
    "build_cost_scenarios",
    "build_replay_request",
]
