"""Chronological cash-equity replay; no implicit daily target rebalancing."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any

import pandas as pd

from .usd_ledger_accounting import (
    TRANSACTION_COLUMNS,
    ZERO,
    settle_usd_rebalance,
    value_usd_book,
)
from .usd_ledger_inputs import (
    require,
    select_usd_fx,
    select_usd_modeled_execution_price,
    select_usd_price,
    validate_usd_request,
)
from .usd_ledger_models import USDRebalanceDecision, USDReplayRequest, USDReplayResult

DAILY_COLUMNS = [
    "valuation_at",
    "cash_usd",
    "positions_usd",
    "nav_usd",
    "local_price_pnl_usd",
    "fx_pnl_usd",
    "costs_usd",
    "nav_return",
]
HOLDING_COLUMNS = [
    "valuation_at",
    "instrument_id",
    "quantity",
    "local_price",
    "usd_per_local",
    "value_usd",
    "weight",
    "price_at",
    "price_available_at",
    "price_source_ref",
    "price_availability_basis",
    "fx_at",
    "fx_available_at",
    "fx_source_ref",
    "fx_availability_basis",
    "session_policy_id",
    "currency",
    "price_unit",
    "fx_base_currency",
    "fx_quote_currency",
    "fx_rate",
    "fx_unit",
    "execution_evidence_kind",
    "modeled_price_session_date",
    "modeled_price_model_id",
    "execution_eligible",
]
MARK_METADATA_COLUMNS = [
    c
    for c in HOLDING_COLUMNS
    if c
    not in (
        "valuation_at",
        "instrument_id",
        "quantity",
        "local_price",
        "usd_per_local",
        "value_usd",
        "weight",
    )
]
TARGET_COLUMNS = [
    "decision_id",
    "decision_at",
    "instrument_id",
    "target_weight",
    "desired_quantity",
    "execution_at",
    "local_price",
    "usd_per_local",
    "decision_nav_usd",
    "event_sequence",
    *MARK_METADATA_COLUMNS,
]


def assert_usd_equal(
    left: Decimal, right: Decimal, field: str, *, scale: Decimal | None = None
) -> None:
    """Allow precision-50 roundoff relative to the largest relevant amount."""
    tolerance_scale = max(Decimal(1), abs(left), abs(right), abs(scale or Decimal(0)))
    tolerance = tolerance_scale * Decimal("1e-45")
    require(abs(left - right) <= tolerance, f"unreconciled {field}")


def _mark_metadata(price, fx, currency) -> dict[str, Any]:
    return {
        "currency": currency,
        "price_unit": price.unit,
        "fx_base_currency": fx.base_currency if fx else "USD",
        "fx_quote_currency": fx.quote_currency if fx else "USD",
        "fx_rate": fx.rate if fx else Decimal(1),
        "fx_unit": fx.unit if fx else "quote_per_base",
        "price_at": price.price_at,
        "price_available_at": price.available_at,
        "price_source_ref": price.source_ref.to_mapping(),
        "price_availability_basis": price.availability_basis,
        "fx_at": fx.price_at if fx else None,
        "fx_available_at": fx.available_at if fx else None,
        "fx_source_ref": fx.source_ref.to_mapping() if fx else None,
        "fx_availability_basis": fx.availability_basis if fx else "usd_identity",
        "session_policy_id": price.session_policy_id,
        "execution_evidence_kind": "verified",
        "modeled_price_session_date": None,
        "modeled_price_model_id": None,
        "execution_eligible": price.execution_eligible and price.availability_basis == "verified",
    }


def _summary(daily: pd.DataFrame, initial_cash: Decimal) -> dict[str, Any]:
    peak, drawdown = initial_cash, ZERO
    for nav in daily.nav_usd:
        peak = max(peak, nav)
        drawdown = max(drawdown, 1 - nav / peak)
    ratio = daily.iloc[-1].nav_usd / initial_cash
    elapsed = Decimal(
        str((daily.iloc[-1].valuation_at - daily.iloc[0].valuation_at).total_seconds())
    )
    cagr = ratio ** (Decimal("31557600") / elapsed) - 1 if elapsed else None
    return {
        "evidence_tier": "diagnostic",
        "return_basis": "usd_price_nav",
        "orders_submitted": False,
        "cumulative_return": ratio - 1,
        "max_drawdown": drawdown,
        "cagr": cagr,
    }


class _Replay:
    def __init__(self, request: USDReplayRequest):
        self.request = request
        self.instruments = {i.instrument_id: i for i in request.instruments}
        self.quantities: dict[str, Decimal] = {}
        self.cash = request.config.initial_cash
        self.prices: dict[str, Decimal] = {}
        self.rates: dict[str, Decimal] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.local_pnl, self.fx_pnl, self.costs = ZERO, ZERO, ZERO
        self.previous_nav = self.cash
        self.daily: list[dict] = []
        self.holdings: list[dict] = []
        self.transactions: list[dict] = []
        self.targets: list[dict] = []
        self.desired: dict[str, Decimal] = {}
        self.events: list[dict] = []

    def audit(self, kind: str, time: datetime, **fields) -> int:
        sequence = len(self.events)
        self.events.append({"kind": kind, "at": time, "sequence": sequence, **fields})
        return sequence

    def mark(self, name: str, time: datetime, *, execution: bool = False) -> None:
        modeled = None
        if execution and self.request.config.allow_modeled_execution_prices:
            modeled = select_usd_modeled_execution_price(self.request, name, time)
            price_value = modeled.reference_price
            metadata = {
                "currency": self.instruments[name].currency,
                "price_unit": modeled.unit,
                "fx_base_currency": "USD",
                "fx_quote_currency": "USD",
                "fx_rate": Decimal(1),
                "fx_unit": "quote_per_base",
                "price_at": modeled.scheduled_open_at,
                "price_available_at": None,
                "price_source_ref": modeled.source_ref.to_mapping(),
                "price_availability_basis": "modeled_reference",
                "fx_at": None,
                "fx_available_at": None,
                "fx_source_ref": None,
                "fx_availability_basis": "usd_identity",
                "session_policy_id": modeled.session_policy_id,
                "execution_evidence_kind": "modeled_reference",
                "modeled_price_session_date": modeled.session_date,
                "modeled_price_model_id": modeled.model_id,
                "execution_eligible": False,
            }
        else:
            price = select_usd_price(self.request, name, time, execution=execution)
            price_value = price.price
            metadata = _mark_metadata(price, None, self.instruments[name].currency)
        rate, fx = select_usd_fx(self.request, self.instruments[name].currency, time)
        if execution and fx is not None:
            require(
                fx.availability_basis == "verified"
                or (
                    modeled is not None
                    and fx.availability_basis == "assumed_market_session"
                    and self.request.config.allow_assumed_availability
                ),
                "FX availability basis cannot fund a transaction",
            )
        if fx is not None:
            metadata.update(
                {
                    "fx_base_currency": fx.base_currency,
                    "fx_quote_currency": fx.quote_currency,
                    "fx_rate": fx.rate,
                    "fx_unit": fx.unit,
                    "fx_at": fx.price_at,
                    "fx_available_at": fx.available_at,
                    "fx_source_ref": fx.source_ref.to_mapping(),
                    "fx_availability_basis": fx.availability_basis,
                }
            )
        quantity = self.quantities.get(name, ZERO)
        old_price, old_rate = self.prices.get(name), self.rates.get(name)
        local_pnl, fx_pnl = ZERO, ZERO
        if quantity:
            local_pnl = (price_value - self.prices[name]) * self.rates[name] * quantity
            fx_pnl = price_value * (rate - self.rates[name]) * quantity
        self.local_pnl += local_pnl
        self.fx_pnl += fx_pnl
        self.prices[name], self.rates[name] = price_value, rate
        self.metadata[name] = metadata
        self.audit(
            "mark",
            time,
            instrument_id=name,
            quantity_before=quantity,
            old_price=old_price,
            old_usd_per_local=old_rate,
            local_price=price_value,
            usd_per_local=rate,
            local_price_pnl_usd=local_pnl,
            fx_pnl_usd=fx_pnl,
            **self.metadata[name],
        )

    def mark_held(self, time: datetime) -> None:
        for name, quantity in self.quantities.items():
            if quantity:
                self.mark(name, time)

    def decide(self, decision: USDRebalanceDecision, time: datetime) -> None:
        for name, weight in sorted(decision.weights.items()):
            if weight:
                self.mark(name, time)
        _, nav = value_usd_book(self.quantities, self.cash, self.prices, self.rates)
        sequence = self.audit("decision", time, decision_id=decision.decision_id, nav_usd=nav)
        self.desired = {}
        for name in sorted(self.instruments):
            weight = decision.weights.get(name, ZERO)
            desired = nav * weight / (self.prices[name] * self.rates[name]) if weight else ZERO
            self.desired[name] = desired
            self.targets.append(
                {
                    "decision_id": decision.decision_id,
                    "decision_at": time,
                    "instrument_id": name,
                    "target_weight": weight,
                    "desired_quantity": desired,
                    "execution_at": decision.execution_times[name],
                    "local_price": self.prices.get(name) if weight else None,
                    "usd_per_local": self.rates.get(name) if weight else None,
                    "decision_nav_usd": nav,
                    "event_sequence": sequence,
                    **(self.metadata[name] if weight else dict.fromkeys(MARK_METADATA_COLUMNS)),
                    "session_policy_id": self.instruments[name].session_policy_id,
                    "currency": self.instruments[name].currency,
                }
            )

    def execute(
        self, decision: USDRebalanceDecision, names: frozenset[str], time: datetime
    ) -> None:
        active = frozenset(n for n in names if self.desired[n] != self.quantities.get(n, ZERO))
        for name in sorted(active):
            self.mark(name, time, execution=True)
        execution_prices = None
        if self.request.config.allow_modeled_execution_prices:
            slippage_rate = self.request.config.slippage_bps / 10000
            execution_prices = {
                name: self.prices[name]
                * (
                    1 + slippage_rate
                    if self.desired[name] > self.quantities.get(name, ZERO)
                    else 1 - slippage_rate
                )
                for name in active
            }
        self.quantities, self.cash, trades = settle_usd_rebalance(
            self.quantities,
            self.cash,
            self.desired,
            self.prices,
            self.rates,
            self.instruments,
            self.request.config,
            execution_ids=active,
            execution_prices=execution_prices,
        )
        for trade in trades.to_dict("records"):
            self.costs += trade["costs_usd"]
            trade.update(self.metadata[trade["instrument_id"]])
            trade.update({"execution_at": time, "decision_id": decision.decision_id})
            trade["event_sequence"] = self.audit(
                "transaction", time, transaction_index=len(self.transactions)
            )
            self.transactions.append(trade)

    def value(self, time: datetime) -> None:
        positions, nav = value_usd_book(self.quantities, self.cash, self.prices, self.rates)
        assert_usd_equal(
            nav - self.previous_nav,
            self.local_pnl + self.fx_pnl - self.costs,
            "interval NAV attribution",
            scale=max(abs(nav), abs(self.previous_nav)),
        )
        self.daily.append(
            {
                "valuation_at": time,
                "cash_usd": self.cash,
                "positions_usd": positions,
                "nav_usd": nav,
                "local_price_pnl_usd": self.local_pnl,
                "fx_pnl_usd": self.fx_pnl,
                "costs_usd": self.costs,
                "nav_return": nav / self.previous_nav - 1,
            }
        )
        for name, quantity in sorted(self.quantities.items()):
            if not quantity:
                continue
            value = quantity * self.prices[name] * self.rates[name]
            self.holdings.append(
                {
                    "valuation_at": time,
                    "instrument_id": name,
                    "quantity": quantity,
                    "local_price": self.prices[name],
                    "usd_per_local": self.rates[name],
                    "value_usd": value,
                    "weight": value / nav,
                    **self.metadata[name],
                }
            )
        self.previous_nav = nav
        self.audit("valuation", time, daily_index=len(self.daily) - 1)
        self.local_pnl, self.fx_pnl, self.costs = ZERO, ZERO, ZERO

    def result(self) -> USDReplayResult:
        daily = pd.DataFrame(self.daily, columns=DAILY_COLUMNS)
        clocks = tuple(
            {"decision_id": d.decision_id, **d.clock.to_mapping()} for d in self.request.decisions
        )
        refs = {
            (r.source_ref.artifact_id, r.source_ref.sha256)
            for r in (*self.request.prices, *self.request.fx)
        }
        refs.update(
            (r.source_ref.artifact_id, r.source_ref.sha256)
            for r in self.request.modeled_execution_prices
        )
        return USDReplayResult(
            daily,
            pd.DataFrame(self.holdings, columns=HOLDING_COLUMNS),
            pd.DataFrame(
                self.transactions,
                columns=[
                    *TRANSACTION_COLUMNS,
                    *MARK_METADATA_COLUMNS,
                    "execution_at",
                    "decision_id",
                    "event_sequence",
                ],
            ),
            pd.DataFrame(self.targets, columns=TARGET_COLUMNS),
            clocks,
            _summary(daily, self.request.config.initial_cash),
            {
                "initial_cash_usd": self.request.config.initial_cash,
                "reconciliation": "passed",
                "decimal_precision": 50,
                "reconciliation_relative_tolerance": "1e-45",
                "sizing_mode": self.request.config.sizing_mode,
                "commission_bps": self.request.config.commission_bps,
                "slippage_bps": self.request.config.slippage_bps,
                "fx_cost_bps": self.request.config.fx_cost_bps,
                "allow_assumed_availability": self.request.config.allow_assumed_availability,
                "modeled_execution_enabled": self.request.config.allow_modeled_execution_prices,
                "source_refs": [{"artifact_id": i, "sha256": h} for i, h in sorted(refs)],
                "events": self.events,
            },
        )


def run_usd_price_replay(request: USDReplayRequest) -> USDReplayResult:
    validate_usd_request(request)
    decisions = {d.clock.decision_at: d for d in request.decisions}
    executions: dict[datetime, list] = defaultdict(list)
    for decision in request.decisions:
        batches: dict[datetime, set[str]] = defaultdict(set)
        for name, time in decision.execution_times.items():
            batches[time].add(name)
        for time, names in batches.items():
            executions[time].append((decision, frozenset(names)))
    valuations = set(request.valuation_times)
    timeline = sorted(valuations | set(decisions) | set(executions))
    with localcontext() as ctx:
        ctx.prec = 50
        replay = _Replay(request)
        for time in timeline:
            replay.mark_held(time)
            if time in decisions:
                replay.decide(decisions[time], time)
            for decision, names in executions.get(time, []):
                replay.execute(decision, names, time)
            if time in valuations:
                replay.value(time)
        return replay.result()
