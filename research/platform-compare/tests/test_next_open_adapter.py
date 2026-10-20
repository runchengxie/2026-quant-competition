from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from exchange_calendars import get_calendar

from platform_compare.accounting.usd_ledger import run_usd_price_replay
from platform_compare.accounting.usd_ledger_models import USDModeledExecutionPrice
from platform_compare.next_open.adapter import (
    ASSET_METADATA,
    CostScenario,
    build_cost_scenarios,
    build_replay_request,
)
from platform_compare.next_open.calendar import (
    first_open_after,
)
from platform_compare.next_open.loader import FX_FILES, NextOpenInputs

D = Decimal
SIGNAL_DATE = date(2026, 3, 10)
CALENDARS = {
    "US": get_calendar("XNYS"),
    "HK": get_calendar("XHKG"),
    "UK": get_calendar("XLON"),
    "AU": get_calendar("XASX"),
    "SG": get_calendar("XSES"),
}


def _inputs(*, future_signal=False):
    sessions = pd.date_range("2026-03-09", "2026-03-12", freq="D")
    assets = {}
    for instrument_id in ASSET_METADATA:
        assets[instrument_id] = pd.DataFrame(
            {
                "date": [stamp.date() for stamp in sessions],
                "open": [D("10")] * len(sessions),
                "high": [D("11")] * len(sessions),
                "low": [D("9")] * len(sessions),
                "close": [D("10.5")] * len(sessions),
                "price_semantics": ["first_regular_hours_trade_open"] * len(sessions),
                "execution_eligible": [False] * len(sessions),
            }
        )
    fx = {
        pair: pd.DataFrame(
            {
                "date": [stamp.date() for stamp in sessions],
                "open": [D(value)] * len(sessions),
                "price_semantics": ["MIDPOINT_DAILY"] * len(sessions),
                "execution_eligible": [False] * len(sessions),
            }
        )
        for pair, value in {
            "AUDUSD": "0.66",
            "GBPUSD": "1.28",
            "USDCAD": "1.37",
            "USDHKD": "7.8",
            "USDSGD": "1.34",
        }.items()
    }
    schedule = {
        "schema_version": "research.target_schedule.v1",
        "strategy_id": "synthetic-defended-rotation",
        "rebalances": [
            {
                "signal_as_of_date": (
                    date(2026, 10, 2) if future_signal else SIGNAL_DATE
                ).isoformat(),
                "targets": [
                    {"instrument_id": "US_SPY", "weight": "0.5"},
                    {"instrument_id": "HK_2800", "weight": "0.25"},
                ],
            }
        ],
    }
    return NextOpenInputs(
        schedule,
        assets,
        fx,
        {
            "dataset_id": "synthetic",
            "analysis_cutoff_local_date": "2026-10-01",
            "execution_eligible": False,
        },
        {"target-schedule-v1.json": "a" * 64}
        | {f"{key}.csv": "b" * 64 for key in assets}
        | dict.fromkeys(FX_FILES.values(), "c" * 64),
    )


def _scenario():
    return CostScenario("commission-5_slippage-5_fx-0", D("5"), D("5"), D("0"), "test")


def test_adapter_uses_latest_input_closes_and_later_market_opens():
    inputs = _inputs()
    request = build_replay_request(
        inputs,
        _scenario(),
        initial_cash=D("100000"),
        max_price_age=timedelta(days=7),
        max_fx_age=timedelta(days=7),
        calendars=CALENDARS,
    )
    decision = request.decisions[0]
    expected = {
        instrument: first_open_after(
            ASSET_METADATA[instrument]["market"],
            decision.clock.decision_at,
            [row.date for row in inputs.assets[instrument].itertuples(index=False)],
            CALENDARS,
        ).scheduled_open_at
        for instrument in ASSET_METADATA
    }
    assert dict(decision.execution_times) == expected
    assert all(value > decision.clock.decision_at for value in expected.values())
    assert decision.clock.information_cutoff_at == decision.clock.decision_at


def test_adapter_marks_daily_open_prices_as_modeled_not_eligible():
    request = build_replay_request(
        _inputs(),
        _scenario(),
        initial_cash=D("100000"),
        max_price_age=timedelta(days=7),
        max_fx_age=timedelta(days=7),
        calendars=CALENDARS,
    )
    assert len(request.modeled_execution_prices) == len(ASSET_METADATA)
    assert all(
        isinstance(row, USDModeledExecutionPrice)
        for row in request.modeled_execution_prices
    )
    assert all(
        row.session_date > SIGNAL_DATE for row in request.modeled_execution_prices
    )
    assert all(
        row.reference_price == D("10") for row in request.modeled_execution_prices
    )
    assert all(
        row.source_ref.sha256 == "b" * 64 for row in request.modeled_execution_prices
    )


def test_adapter_marks_daily_fx_open_as_assumed_market_session():
    request = build_replay_request(
        _inputs(),
        _scenario(),
        initial_cash=D("100000"),
        max_price_age=timedelta(days=7),
        max_fx_age=timedelta(days=7),
        calendars=CALENDARS,
    )
    observations = {row.base_currency + row.quote_currency: row for row in request.fx}
    assert observations["USDHKD"].availability_basis == "assumed_market_session"
    assert observations["USDHKD"].rate == D("7.8")
    assert observations["USDSGD"].availability_basis == "assumed_market_session"
    assert observations["USDSGD"].rate == D("1.34")
    assert observations["GBPUSD"].rate == D("1.28")
    assert observations["AUDUSD"].rate == D("0.66")
    assert all(row.availability_basis != "verified" for row in request.fx)


def test_cost_scenarios_are_exact_36_combinations():
    scenarios = build_cost_scenarios()
    assert len(scenarios) == 36
    assert {
        (row.commission_bps, row.slippage_bps, row.fx_cost_bps) for row in scenarios
    } == {
        (D(commission), D(slippage), D(fx))
        for commission in (0, 5, 10)
        for slippage in (0, 5, 10, 20)
        for fx in (0, 5, 10)
    }
    reference = [
        row
        for row in scenarios
        if (row.commission_bps, row.slippage_bps, row.fx_cost_bps) == (D(5), D(5), D(0))
    ]
    assert len(reference) == 1
    assert "optimistic" in reference[0].label.lower()


def test_adapter_does_not_emit_xiu_or_future_data():
    inputs = _inputs()
    request = build_replay_request(
        inputs,
        _scenario(),
        initial_cash=D("100000"),
        max_price_age=timedelta(days=7),
        max_fx_age=timedelta(days=7),
        calendars=CALENDARS,
    )
    assert {row.instrument_id for row in request.instruments} == set(ASSET_METADATA)
    assert "CA_XIU" not in {row.instrument_id for row in request.instruments}
    assert all(row.price_at.date() <= date(2026, 10, 1) for row in request.prices)
    with pytest.raises(ValueError, match="after the cutoff"):
        build_replay_request(
            _inputs(future_signal=True),
            _scenario(),
            initial_cash=D("100000"),
            max_price_age=timedelta(days=7),
            max_fx_age=timedelta(days=7),
            calendars=CALENDARS,
        )


def test_adapter_replays_only_diagnostic_modeled_transactions():
    request = build_replay_request(
        _inputs(),
        _scenario(),
        initial_cash=D("100000"),
        max_price_age=timedelta(days=7),
        max_fx_age=timedelta(days=7),
        calendars=CALENDARS,
    )
    result = run_usd_price_replay(request)
    assert result.summary["orders_submitted"] is False
    assert result.summary["evidence_tier"] == "diagnostic"
    assert set(result.transactions.execution_evidence_kind) == {"modeled_reference"}
    assert not result.transactions.execution_eligible.astype(bool).any()
    foreign = result.transactions.loc[result.transactions.currency != "USD"]
    assert set(foreign.fx_availability_basis) == {"assumed_market_session"}
    identity = result.transactions.loc[result.transactions.currency == "USD"]
    assert set(identity.fx_availability_basis) == {"usd_identity"}
