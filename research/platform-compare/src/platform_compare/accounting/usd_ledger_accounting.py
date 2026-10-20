"""Decimal quantity valuation and cash-constrained modeled transactions."""

from collections.abc import Mapping
from decimal import ROUND_DOWN, Decimal, localcontext

import pandas as pd

from .usd_ledger_inputs import decimal_value, require, validate_usd_config
from .usd_ledger_models import USDInstrument, USDReplayConfig

ZERO = Decimal(0)
QUANTITY_STEP = Decimal("0.000000000001")
TRANSACTION_COLUMNS = [
    "instrument_id",
    "requested_delta",
    "executed_delta",
    "local_price",
    "execution_price",
    "usd_per_local",
    "notional_usd",
    "commission_usd",
    "slippage_usd",
    "fx_cost_usd",
    "costs_usd",
    "buy_scale",
    "cash_after_usd",
]


def value_usd_book(
    quantities: Mapping[str, Decimal],
    cash: Decimal,
    local_prices: Mapping[str, Decimal],
    usd_per_local: Mapping[str, Decimal],
) -> tuple[Decimal, Decimal]:
    decimal_value(cash, "cash")
    with localcontext() as ctx:
        ctx.prec = 50
        positions = ZERO
        for name, quantity in quantities.items():
            decimal_value(quantity, "quantity")
            if quantity == 0:
                continue
            require(name in local_prices and name in usd_per_local, "missing held-asset mark")
            price = decimal_value(local_prices[name], "price", positive=True)
            fx = decimal_value(usd_per_local[name], "FX", positive=True)
            positions += quantity * price * fx
        return positions, cash + positions


def _round_increment(
    quantity: Decimal, instrument: USDInstrument, config: USDReplayConfig
) -> Decimal:
    step = Decimal(instrument.lot_size) if config.sizing_mode == "integral" else QUANTITY_STEP
    return (quantity / step).to_integral_value(rounding=ROUND_DOWN) * step


def _rates(instrument: USDInstrument, config: USDReplayConfig) -> tuple[Decimal, ...]:
    return (
        config.commission_bps / 10000,
        config.slippage_bps / 10000,
        ZERO if instrument.currency == "USD" else config.fx_cost_bps / 10000,
    )


def _validate_settlement(quantities, cash, desired, prices, fx, instruments, config, ids):
    validate_usd_config(config)
    decimal_value(cash, "cash")
    require(isinstance(ids, frozenset) and ids <= set(instruments), "invalid execution IDs")
    require(
        set(quantities) <= set(instruments) and set(desired) <= set(instruments),
        "unknown quantity instrument",
    )
    for quantity in quantities.values():
        decimal_value(quantity, "quantity")
    for quantity in desired.values():
        decimal_value(quantity, "desired quantity")
    for name in ids:
        require(name in desired and name in prices and name in fx, "missing batch inputs")
        decimal_value(prices[name], "price", positive=True)
        decimal_value(fx[name], "FX", positive=True)
        ins = instruments[name]
        require(
            isinstance(ins, USDInstrument) and ins.instrument_id == name,
            "instrument identity mismatch",
        )
        require(ins.asset_type in ("equity", "etf"), "unsupported asset")
        require(type(ins.lot_size) is int and ins.lot_size > 0, "invalid lot")


def _apply_transaction(
    name, delta, requested, cash, quantities, price, fx, rates, scale, execution_price=None
):
    notional = abs(delta) * price * fx
    commission_rate, slippage_rate, fx_cost_rate = rates
    commission = notional * commission_rate
    fx_cost = notional * fx_cost_rate
    effective_price = price if execution_price is None else execution_price
    slippage = (
        notional * slippage_rate
        if execution_price is None
        else abs(delta) * abs(effective_price - price) * fx
    )
    costs = commission + slippage + fx_cost
    cash -= delta * effective_price * fx + commission + fx_cost
    if execution_price is None:
        cash -= slippage
    quantities[name] = quantities.get(name, ZERO) + delta
    require(cash >= 0 and quantities[name] >= 0, "settlement would borrow or oversell")
    return cash, {
        "instrument_id": name,
        "requested_delta": requested,
        "executed_delta": delta,
        "local_price": price,
        "execution_price": effective_price,
        "usd_per_local": fx,
        "notional_usd": notional,
        "commission_usd": commission,
        "slippage_usd": slippage,
        "fx_cost_usd": fx_cost,
        "costs_usd": costs,
        "buy_scale": scale,
        "cash_after_usd": cash,
    }


def settle_usd_rebalance(
    quantities: Mapping[str, Decimal],
    cash: Decimal,
    desired_quantities: Mapping[str, Decimal],
    local_prices: Mapping[str, Decimal],
    usd_per_local: Mapping[str, Decimal],
    instruments: Mapping[str, USDInstrument],
    config: USDReplayConfig,
    *,
    execution_ids: frozenset[str],
    execution_prices: Mapping[str, Decimal] | None = None,
) -> tuple[dict[str, Decimal], Decimal, pd.DataFrame]:
    _validate_settlement(
        quantities,
        cash,
        desired_quantities,
        local_prices,
        usd_per_local,
        instruments,
        config,
        execution_ids,
    )
    execution_prices = {} if execution_prices is None else execution_prices
    require(isinstance(execution_prices, Mapping), "execution_prices must be a mapping")
    require(set(execution_prices) <= set(execution_ids), "execution price outside execution IDs")
    for value in execution_prices.values():
        decimal_value(value, "execution price", positive=True)
    with localcontext() as ctx:
        ctx.prec = 50
        book, rows = dict(quantities), []
        deltas = {
            name: desired_quantities[name] - book.get(name, ZERO) for name in sorted(execution_ids)
        }
        for name, delta in deltas.items():
            if delta >= 0:
                continue
            sell = (
                -delta
                if desired_quantities[name] == 0
                else _round_increment(-delta, instruments[name], config)
            )
            cash, row = _apply_transaction(
                name,
                -sell,
                delta,
                cash,
                book,
                local_prices[name],
                usd_per_local[name],
                _rates(instruments[name], config),
                Decimal(1),
                execution_prices.get(name),
            )
            rows.append(row)
        buys = {
            name: _round_increment(delta, instruments[name], config)
            for name, delta in deltas.items()
            if delta > 0
        }
        required = ZERO
        for name, quantity in buys.items():
            commission_rate, slippage_rate, fx_cost_rate = _rates(instruments[name], config)
            if name in execution_prices:
                required += (
                    quantity
                    * usd_per_local[name]
                    * (
                        execution_prices[name]
                        + local_prices[name] * (commission_rate + fx_cost_rate)
                    )
                )
            else:
                buy_price = local_prices[name]
                extra_cost_rate = commission_rate + slippage_rate + fx_cost_rate
                required += quantity * buy_price * usd_per_local[name] * (1 + extra_cost_rate)
        scale = min(Decimal(1), cash / required) if required else Decimal(1)
        for name, quantity in buys.items():
            executed = _round_increment(quantity * scale, instruments[name], config)
            cash, row = _apply_transaction(
                name,
                executed,
                deltas[name],
                cash,
                book,
                local_prices[name],
                usd_per_local[name],
                _rates(instruments[name], config),
                scale,
                execution_prices.get(name),
            )
            rows.append(row)
        return book, cash, pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)
