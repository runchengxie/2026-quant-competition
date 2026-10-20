# Derived from quant-platform 28a32ba707ad72d1eb68cde5075663e1b3819ac7.
# Modified for the competition namespace/identity; licensed under Apache-2.0.
# See accounting/ORIGIN.json and LICENSE-APACHE-2.0.txt for provenance and terms.
"""Reconcile Decimal evidence before the existing diagnostic bundle writer."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, cast

import pandas as pd
from platform_compare.accounting.contracts import ArtifactRef, ResearchClock

from .backtest_bundle import BacktestBundleManifest, BacktestEvidenceTier
from .backtest_bundle_io import write_backtest_bundle
from .execution_sim.results import UnifiedLedger
from .usd_ledger import DAILY_COLUMNS, HOLDING_COLUMNS, TARGET_COLUMNS, _summary, assert_usd_equal
from .usd_ledger_accounting import TRANSACTION_COLUMNS, ZERO, value_usd_book
from .usd_ledger_inputs import decimal_value, require, utc_time
from .usd_ledger_models import USDReplayResult


def _signed(value: Any, field: str) -> Decimal:
    require(isinstance(value, Decimal) and value.is_finite(), f"{field} must be finite Decimal")
    return value


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    return value


def _evidence(payload: Any) -> None:
    if not isinstance(payload, Mapping):
        return
    expected = {
        "evidence_tier": "diagnostic",
        "return_basis": "usd_price_nav",
        "orders_submitted": False,
        "order_lifecycle": False,
        "total_return": False,
    }
    for key, value in payload.items():
        if key in expected:
            require(
                type(value) is type(expected[key]) and value == expected[key],
                "unsupported evidence/capability override",
            )
        if isinstance(value, Mapping):
            _evidence(value)


def _frame(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    require(
        isinstance(frame, pd.DataFrame) and set(columns) <= set(frame.columns),
        f"invalid {label} table",
    )


def _root_clock(result: USDReplayResult, root: ResearchClock) -> None:
    require(isinstance(root, ResearchClock), "ResearchClock required")
    ResearchClock.from_mapping(root.to_mapping())
    for key, value in vars(root).items():
        if key.endswith("_at") and value is not None:
            utc_time(value)
    require(
        root.timezone == "UTC" and root.valuation_at == result.daily.iloc[-1].valuation_at,
        "root valuation clock mismatch",
    )
    if not result.decision_clocks:
        require(
            root.decision_at <= result.daily.iloc[0].valuation_at, "all-cash root clock mismatch"
        )
        return
    clocks = [ResearchClock.from_mapping(c) for c in result.decision_clocks]
    require(root.decision_at == clocks[0].decision_at, "root decision clock mismatch")
    require(
        root.execution_window_start_at is not None and root.execution_window_end_at is not None,
        "root execution bounds required",
    )
    for clock in clocks:
        require(
            clock.execution_window_start_at is not None
            and clock.execution_window_end_at is not None,
            "per-decision bounds required",
        )
        require(
            cast(datetime, root.execution_window_start_at)
            <= cast(datetime, clock.execution_window_start_at)
            and cast(datetime, root.execution_window_end_at)
            >= cast(datetime, clock.execution_window_end_at),
            "root must cover every execution window",
        )


def _metadata(row: Mapping, time: datetime, lineage: set, *, execution: bool = False) -> None:
    require(
        row["price_unit"] == "currency_per_share" and row["fx_unit"] == "quote_per_base",
        "invalid observation units",
    )
    evidence_kind = row.get("execution_evidence_kind", "verified")
    modeled = evidence_kind == "modeled_reference"
    eligible = row.get("execution_eligible", True)
    require(
        isinstance(eligible, bool) or type(eligible).__name__ == "bool_",
        "invalid execution eligibility flag",
    )
    if modeled:
        require(
            utc_time(row["price_at"]) == time
            and pd.isna(row["price_available_at"])
            and not bool(eligible)
            and (
                type(row["modeled_price_session_date"]) is date
                or isinstance(row["modeled_price_session_date"], pd.Timestamp)
            )
            and isinstance(row["modeled_price_model_id"], str)
            and bool(row["modeled_price_model_id"].strip()),
            "invalid modeled price reference metadata",
        )
    else:
        require(
            evidence_kind == "verified"
            and bool(pd.isna(row.get("modeled_price_session_date")))
            and bool(pd.isna(row.get("modeled_price_model_id")))
            and utc_time(row["price_at"]) <= utc_time(row["price_available_at"]) <= time,
            "unavailable or invalid verified price evidence",
        )
    ref = ArtifactRef.from_mapping(row["price_source_ref"])
    require((ref.artifact_id, ref.sha256) in lineage, "unlisted price lineage")
    if execution:
        if modeled:
            require(
                row["price_availability_basis"] == "modeled_reference",
                "invalid modeled price basis",
            )
        else:
            require(
                row["price_at"] == time
                and row["price_availability_basis"] == "verified"
                and bool(eligible),
                "ineligible execution evidence",
            )
    rate = decimal_value(row["fx_rate"], "raw FX", positive=True)
    if row["currency"] == "USD":
        require(
            row["fx_source_ref"] is None
            and row["fx_base_currency"] == "USD"
            and row["fx_quote_currency"] == "USD"
            and rate == 1,
            "invalid USD identity evidence",
        )
        expected = Decimal(1)
    else:
        pair = (row["fx_base_currency"], row["fx_quote_currency"])
        currency = row["currency"]
        require(pair in ((currency, "USD"), ("USD", currency)), "invalid FX direction")
        require(
            row["fx_availability_basis"]
            in ("verified", "assumed_date_lag", "assumed_market_session"),
            "invalid FX availability basis",
        )
        require(
            utc_time(row["fx_at"]) <= utc_time(row["fx_available_at"]) <= time,
            "unavailable FX evidence",
        )
        ref = ArtifactRef.from_mapping(row["fx_source_ref"])
        require((ref.artifact_id, ref.sha256) in lineage, "unlisted FX lineage")
        if execution:
            require(
                row["fx_availability_basis"] == "verified"
                or (modeled and row["fx_availability_basis"] == "assumed_market_session"),
                "assumed FX execution",
            )
        expected = rate if pair[0] == currency else Decimal(1) / rate
    assert_usd_equal(
        decimal_value(row["usd_per_local"], "conversion", positive=True), expected, "FX direction"
    )


def _validate_daily(result: USDReplayResult) -> None:
    previous = decimal_value(result.diagnostics["initial_cash_usd"], "initial cash", positive=True)
    times = [utc_time(t) for t in result.daily.valuation_at]
    require(times == sorted(set(times)) and bool(times), "invalid valuation grid")
    for row in result.daily.to_dict("records"):
        for key in ("cash_usd", "positions_usd", "nav_usd", "costs_usd"):
            decimal_value(row[key], key)
        local = _signed(row["local_price_pnl_usd"], "local PnL")
        fx = _signed(row["fx_pnl_usd"], "FX PnL")
        ret = _signed(row["nav_return"], "NAV return")
        assert_usd_equal(row["nav_usd"], row["cash_usd"] + row["positions_usd"], "cash + positions")
        assert_usd_equal(
            row["nav_usd"] - previous,
            local + fx - row["costs_usd"],
            "NAV attribution",
            scale=max(abs(row["nav_usd"]), abs(previous)),
        )
        assert_usd_equal(ret, row["nav_usd"] / previous - 1, "NAV return")
        previous = row["nav_usd"]


def _transaction(
    row: Mapping,
    cash: Decimal,
    book: dict[str, Decimal],
    result: USDReplayResult,
    lineage: set,
    target: Mapping,
) -> Decimal:
    time = utc_time(row["execution_at"])
    _metadata(row, time, lineage, execution=True)
    name, delta = row["instrument_id"], _signed(row["executed_delta"], "executed delta")
    requested = _signed(row["requested_delta"], "requested delta")
    require(target["execution_at"] == time, "transaction schedule mismatch")
    assert_usd_equal(
        requested, target["desired_quantity"] - book.get(name, ZERO), "requested delta"
    )
    require(
        delta == 0 or (delta * requested > 0 and abs(delta) <= abs(requested)),
        "executed delta exceeds request",
    )
    modeled = row["execution_evidence_kind"] == "modeled_reference"
    require(
        modeled is bool(result.diagnostics.get("modeled_execution_enabled")),
        "transaction evidence class conflicts with replay mode",
    )
    if row["fx_availability_basis"] == "assumed_market_session":
        require(
            modeled
            and result.diagnostics.get("allow_assumed_availability") is True
            and result.diagnostics.get("modeled_execution_enabled") is True,
            "assumed market-session FX opt-ins are missing",
        )
    notional = (
        abs(delta)
        * decimal_value(row["local_price"], "price", positive=True)
        * row["usd_per_local"]
    )
    assert_usd_equal(decimal_value(row["notional_usd"], "notional"), notional, "trade notional")
    execution_price = decimal_value(row["execution_price"], "execution price", positive=True)
    if modeled:
        rate = decimal_value(result.diagnostics["slippage_bps"], "slippage_bps") / 10000
        fill_direction = delta if delta else requested
        expected_execution_price = row["local_price"] * (
            1 + rate if fill_direction >= 0 else 1 - rate
        )
        assert_usd_equal(execution_price, expected_execution_price, "signed modeled slippage price")
    else:
        assert_usd_equal(execution_price, row["local_price"], "verified reference price")
    components = []
    for key, rate_key in (
        ("commission_usd", "commission_bps"),
        ("slippage_usd", "slippage_bps"),
        ("fx_cost_usd", "fx_cost_bps"),
    ):
        rate = decimal_value(result.diagnostics[rate_key], rate_key)
        expected = (
            ZERO if key == "fx_cost_usd" and row["currency"] == "USD" else notional * rate / 10000
        )
        if key == "slippage_usd" and modeled:
            expected = abs(delta) * abs(execution_price - row["local_price"]) * row["usd_per_local"]
        cost = decimal_value(row[key], key)
        assert_usd_equal(cost, expected, key)
        components.append(cost)
    cost = decimal_value(row["costs_usd"], "costs")
    assert_usd_equal(cost, sum(components, ZERO), "cost components")
    book[name] = book.get(name, ZERO) + delta
    cash -= (
        delta * execution_price * row["usd_per_local"] + row["commission_usd"] + row["fx_cost_usd"]
    )
    if not modeled:
        cash -= row["slippage_usd"]
    require(book[name] >= 0 and cash >= 0, "inventory/cash must be nonnegative")
    assert_usd_equal(cash, row["cash_after_usd"], "transaction cash")
    return cash


def _holdings(
    rows: list[Mapping], time: datetime, nav: Decimal, book: dict, lineage: set
) -> Decimal:
    names = [r["instrument_id"] for r in rows]
    require(len(names) == len(set(names)), "duplicate holdings")
    require(set(names) == {n for n, q in book.items() if q}, "holdings coverage mismatch")
    total = ZERO
    for row in rows:
        _metadata(row, time, lineage)
        quantity = decimal_value(row["quantity"], "held quantity", positive=True)
        price = decimal_value(row["local_price"], "held price", positive=True)
        value = decimal_value(row["value_usd"], "held value", positive=True)
        assert_usd_equal(quantity, book[row["instrument_id"]], "held quantity")
        assert_usd_equal(value, quantity * price * row["usd_per_local"], "held value")
        assert_usd_equal(decimal_value(row["weight"], "weight"), value / nav, "held weight")
        total += value
    return total


class _EvidenceReplay:
    """Independently recompute ordered financial evidence at publication."""

    def __init__(self, result: USDReplayResult, lineage: set):
        self.result, self.lineage = result, lineage
        self.cash = result.diagnostics["initial_cash_usd"]
        self.book: dict[str, Decimal] = {}
        self.prices: dict[str, Decimal] = {}
        self.rates: dict[str, Decimal] = {}
        self.marks: dict[str, Mapping] = {}
        self.local_pnl, self.fx_pnl, self.costs = ZERO, ZERO, ZERO
        self.clocks = {c["decision_id"]: c for c in result.decision_clocks}
        self.targets = {
            (r["decision_id"], r["instrument_id"]): r for r in result.targets.to_dict("records")
        }
        require(len(self.targets) == len(result.targets), "duplicate targets")
        self.transactions = result.transactions.to_dict("records")
        self.tx_cursor, self.daily_cursor = 0, 0
        self.decisions: set[str] = set()
        self.executed: set[tuple[str, str]] = set()

    def mark(self, event: Mapping) -> None:
        name, time = event["instrument_id"], event["at"]
        _metadata(event, time, self.lineage)
        quantity = decimal_value(event["quantity_before"], "mark quantity")
        assert_usd_equal(quantity, self.book.get(name, ZERO), "pre-mark quantity")
        require(
            event["old_price"] == self.prices.get(name)
            and event["old_usd_per_local"] == self.rates.get(name),
            "mark chain mismatch",
        )
        price = decimal_value(event["local_price"], "event price", positive=True)
        fx = decimal_value(event["usd_per_local"], "event FX", positive=True)
        local = (price - self.prices[name]) * self.rates[name] * quantity if quantity else ZERO
        fx_pnl = price * (fx - self.rates[name]) * quantity if quantity else ZERO
        assert_usd_equal(
            _signed(event["local_price_pnl_usd"], "event local PnL"), local, "event local PnL"
        )
        assert_usd_equal(_signed(event["fx_pnl_usd"], "event FX PnL"), fx_pnl, "event FX PnL")
        self.local_pnl += local
        self.fx_pnl += fx_pnl
        self.prices[name], self.rates[name], self.marks[name] = price, fx, event

    def decision(self, event: Mapping) -> None:
        name, time = event["decision_id"], event["at"]
        require(
            name in self.clocks and name not in self.decisions, "unknown/repeated decision event"
        )
        require(
            ResearchClock.from_mapping(self.clocks[name]).decision_at == time,
            "decision event clock mismatch",
        )
        self.decisions.add(name)
        _, nav = value_usd_book(self.book, self.cash, self.prices, self.rates)
        assert_usd_equal(
            decimal_value(event["nav_usd"], "decision NAV", positive=True),
            nav,
            "decision NAV snapshot",
        )
        for (decision_id, instrument), target in self.targets.items():
            if decision_id != name:
                continue
            require(target["event_sequence"] == event["sequence"], "target event mismatch")
            assert_usd_equal(
                decimal_value(target["decision_nav_usd"], "target NAV", positive=True),
                nav,
                "target decision NAV",
            )
            weight = target["target_weight"]
            if weight:
                _metadata(target, time, self.lineage)
                self.match_mark(target, instrument)
                desired = nav * weight / (self.prices[instrument] * self.rates[instrument])
                assert_usd_equal(target["desired_quantity"], desired, "frozen target sizing")

    def match_mark(self, row: Mapping, name: str) -> None:
        from .usd_ledger import MARK_METADATA_COLUMNS

        require(name in self.marks, "missing selected mark evidence")
        for field in ("local_price", "usd_per_local", *MARK_METADATA_COLUMNS):
            left, right = row[field], self.marks[name][field]
            equal = (pd.isna(left) and pd.isna(right)) or left == right
            require(
                equal,
                f"selected mark evidence mismatch: {field}",
            )

    def transaction(self, event: Mapping) -> None:
        require(
            event["transaction_index"] == self.tx_cursor
            and self.tx_cursor < len(self.transactions),
            "transaction event coverage mismatch",
        )
        tx = self.transactions[self.tx_cursor]
        require(
            tx["event_sequence"] == event["sequence"] and tx["execution_at"] == event["at"],
            "transaction event clock mismatch",
        )
        key = (tx["decision_id"], tx["instrument_id"])
        require(
            key in self.targets and key not in self.executed and key[0] in self.decisions,
            "unknown/repeated transaction event",
        )
        self.executed.add(key)
        self.match_mark(tx, key[1])
        self.cash = _transaction(
            tx, self.cash, self.book, self.result, self.lineage, self.targets[key]
        )
        self.costs += tx["costs_usd"]
        self.tx_cursor += 1

    def valuation(self, event: Mapping) -> None:
        require(
            event["daily_index"] == self.daily_cursor
            and self.daily_cursor < len(self.result.daily),
            "valuation event coverage mismatch",
        )
        daily = self.result.daily.iloc[self.daily_cursor]
        require(daily.valuation_at == event["at"], "valuation event clock mismatch")
        positions, nav = value_usd_book(self.book, self.cash, self.prices, self.rates)
        assert_usd_equal(daily.cash_usd, self.cash, "event cash")
        assert_usd_equal(daily.positions_usd, positions, "event positions")
        assert_usd_equal(daily.nav_usd, nav, "event NAV")
        assert_usd_equal(daily.local_price_pnl_usd, self.local_pnl, "independent local PnL")
        assert_usd_equal(daily.fx_pnl_usd, self.fx_pnl, "independent FX PnL")
        assert_usd_equal(daily.costs_usd, self.costs, "event costs")
        rows = self.result.holdings[self.result.holdings.valuation_at == event["at"]].to_dict(
            "records"
        )
        total = _holdings(rows, event["at"], nav, self.book, self.lineage)
        assert_usd_equal(total, positions, "aggregate holdings")
        for row in rows:
            self.match_mark(row, row["instrument_id"])
        self.local_pnl, self.fx_pnl, self.costs = ZERO, ZERO, ZERO
        self.daily_cursor += 1


def _reconcile_events(result: USDReplayResult, lineage: set) -> None:
    events = result.diagnostics.get("events")
    require(isinstance(events, list) and bool(events), "ordered accounting events required")
    events = cast(list[Mapping[str, Any]], events)
    replay = _EvidenceReplay(result, lineage)
    previous_time = result.daily.iloc[0].valuation_at
    handlers = {
        "mark": replay.mark,
        "decision": replay.decision,
        "transaction": replay.transaction,
        "valuation": replay.valuation,
    }
    for index, event in enumerate(events):
        require(
            isinstance(event, Mapping)
            and type(event.get("sequence")) is int
            and event["sequence"] == index,
            "invalid event sequence",
        )
        time = utc_time(event["at"])
        require(
            previous_time <= time <= result.daily.iloc[-1].valuation_at,
            "accounting events must be chronological and within grid",
        )
        require(event["kind"] in handlers, "unsupported accounting event")
        handlers[event["kind"]](event)
        previous_time = time
    require(
        replay.tx_cursor == len(result.transactions)
        and replay.daily_cursor == len(result.daily)
        and replay.decisions == set(replay.clocks),
        "incomplete accounting event coverage",
    )
    require(events[-1]["kind"] == "valuation", "terminal valuation evidence required")
    require(
        set(result.holdings.valuation_at) <= set(result.daily.valuation_at), "off-grid holdings"
    )


def _validate_result(result: USDReplayResult, input_refs: Sequence[Mapping[str, Any]]) -> None:
    require(isinstance(result, USDReplayResult), "USDReplayResult required")
    for field, columns in (
        ("daily", DAILY_COLUMNS),
        ("holdings", HOLDING_COLUMNS),
        ("transactions", [*TRANSACTION_COLUMNS, "execution_at", "decision_id"]),
        ("targets", TARGET_COLUMNS),
    ):
        _frame(getattr(result, field), columns, field)
    require(not result.daily.empty and bool(input_refs), "nonempty daily/lineage inputs required")
    require(
        type(result.diagnostics.get("modeled_execution_enabled")) is bool
        and type(result.diagnostics.get("allow_assumed_availability")) is bool,
        "invalid replay opt-in diagnostics",
    )
    lineage = {(ref.artifact_id, ref.sha256) for ref in map(ArtifactRef.from_mapping, input_refs)}
    sources = {
        (ref.artifact_id, ref.sha256)
        for ref in map(ArtifactRef.from_mapping, result.diagnostics["source_refs"])
    }
    require(sources <= lineage, "source lineage mismatch")
    for key in ("evidence_tier", "return_basis", "orders_submitted"):
        require(key in result.summary, "missing authoritative evidence label")
    _evidence(result.summary)
    _evidence(result.diagnostics)
    if any(
        event.get("fx_availability_basis") == "assumed_market_session"
        for event in result.diagnostics.get("events", [])
    ):
        require(
            result.diagnostics.get("allow_assumed_availability") is True
            and result.diagnostics.get("modeled_execution_enabled") is True,
            "assumed market-session FX opt-ins are missing",
        )
    _validate_schedule(result)
    _validate_daily(result)
    _reconcile_events(result, lineage)
    expected = _summary(result.daily, result.diagnostics["initial_cash_usd"])
    for key in ("cumulative_return", "max_drawdown", "cagr"):
        require(key in result.summary, "missing performance metric")
        if expected[key] is None:
            require(result.summary[key] is None, "undefined metric must remain undefined")
        else:
            assert_usd_equal(_signed(result.summary[key], key), expected[key], key)


def _validate_schedule(result: USDReplayResult) -> None:
    clocks, previous_end = {}, None
    for record in result.decision_clocks:
        name = record.get("decision_id")
        require(
            isinstance(name, str) and bool(name.strip()) and name not in clocks,
            "invalid or duplicate decision identity",
        )
        clock = ResearchClock.from_mapping(record)
        require(clock.timezone == "UTC", "decision timezone must be UTC")
        for key, value in vars(clock).items():
            if key.endswith("_at") and value is not None:
                utc_time(value)
        require(
            previous_end is None or clock.decision_at > previous_end,
            "overlapping decision evidence",
        )
        require(
            clock.earliest_order_at is not None
            and clock.execution_window_start_at is not None
            and clock.execution_window_end_at is not None,
            "decision execution bounds required",
        )
        clocks[name] = clock
        previous_end = clock.execution_window_end_at
    universes, weights = {}, {}
    for row in result.targets.to_dict("records"):
        name = row["decision_id"]
        require(name in clocks, "unknown target decision")
        clock = clocks[name]
        require(row["decision_at"] == clock.decision_at, "target decision timestamp mismatch")
        time = utc_time(row["execution_at"])
        require(
            time > clock.decision_at
            and time >= cast(datetime, clock.earliest_order_at)
            and cast(datetime, clock.execution_window_start_at)
            <= time
            <= cast(datetime, clock.execution_window_end_at),
            "target execution clock mismatch",
        )
        weight = decimal_value(row["target_weight"], "target weight")
        decimal_value(row["desired_quantity"], "desired quantity")
        require(weight != 0 or row["desired_quantity"] == 0, "zero target must liquidate")
        weights[name] = weights.get(name, ZERO) + weight
        universes.setdefault(name, set()).add(row["instrument_id"])
    require(all(w <= 1 for w in weights.values()), "target weights exceed one")
    sets = [universes.get(name, set()) for name in clocks]
    require(not sets or all(s == sets[0] for s in sets), "decision universe coverage mismatch")


def _ledger(result: USDReplayResult) -> UnifiedLedger:
    # Decimal strings preserve the authoritative values in Parquet, independently of
    # the existing generic reconciliation's float conversion. Full records live in JSON.
    dates = [t.isoformat() for t in result.daily.valuation_at]

    def frame(column: str, name: str) -> pd.DataFrame:
        return pd.DataFrame({"trade_date": dates, name: [str(v) for v in result.daily[column]]})

    return UnifiedLedger(
        targets=pd.DataFrame(_json(result.targets.to_dict("records"))),
        orders=pd.DataFrame(),
        fills=pd.DataFrame(),
        daily_positions=frame("positions_usd", "positions_value"),
        daily_cash=frame("cash_usd", "cash"),
        daily_nav=frame("nav_usd", "nav"),
        cost_breakdown=pd.DataFrame(
            {"trade_date": dates, "transaction_cost": [str(v) for v in result.daily.costs_usd]}
        ),
        turnover_breakdown=pd.DataFrame(
            {"filled_notional": [str(v) for v in result.transactions.notional_usd]}
        ),
    )


def write_usd_price_replay_bundle(
    output_dir: Path,
    *,
    result: USDReplayResult,
    run_id: str,
    research_clock: ResearchClock,
    producer: Mapping[str, Any],
    configuration_sha256: str,
    input_refs: Sequence[Mapping[str, Any]],
) -> BacktestBundleManifest:
    with localcontext() as ctx:
        ctx.prec = 50
        _validate_result(result, input_refs)
        _root_clock(result, research_clock)
        diagnostics = {
            "summary": result.summary,
            "accounting": result.diagnostics,
            "daily": result.daily.to_dict("records"),
            "holdings": result.holdings.to_dict("records"),
            "transactions": result.transactions.to_dict("records"),
            "targets": result.targets.to_dict("records"),
            "decision_clocks": result.decision_clocks,
            "usd_reconciliation": {
                "status": "passed",
                "decimal_precision": 50,
                "relative_tolerance": "1e-45",
            },
        }
        return write_backtest_bundle(
            output_dir,
            run_id=run_id,
            evidence_tier=BacktestEvidenceTier.DIAGNOSTIC,
            ledger=_ledger(result),
            research_clock=research_clock.to_mapping(),
            backend={"name": "competition.usd_price_ledger", "version": "1"},
            backend_capabilities={
                "order_lifecycle": False,
                "daily_ledger": True,
                "partial_fills": False,
                "long_short": False,
            },
            producer=producer,
            configuration_sha256=configuration_sha256,
            input_refs=input_refs,
            diagnostics=_json(diagnostics),
        )
