"""Long-only daily holdings with cash-funded fees and marked weight drift."""

import math
from statistics import mean, stdev

from crypto_mm.data.daily_prices import _number, validate_prices as validate_prices


def account_periods(
    prices: dict,
    targets: list[dict],
    *,
    fee_bps: float,
    quote_currency: str,
    decision_flags: list[bool] | None = None,
) -> dict:
    if (
        quote_currency not in {"USD", "HKD", "USDT"}
        or not _number(fee_bps)
        or not 0 <= fee_bps <= 100
    ):
        raise ValueError("INVALID_ACCOUNTING_IDENTITY")
    validate_prices(prices)
    dates, closes = prices["dates"], prices["close"]
    if not isinstance(targets, list) or len(targets) != len(dates) - 1:
        raise ValueError("INVALID_ACCOUNTING_GRID")
    if decision_flags is not None and (
        not isinstance(decision_flags, list)
        or len(decision_flags) != len(targets)
        or any(type(flag) is not bool for flag in decision_flags)
    ):
        raise ValueError("INVALID_ACCOUNTING_DECISIONS")
    products = sorted(closes)
    for target in targets:
        if (
            not isinstance(target, dict)
            or not set(target) <= set(products)
            or any(not _number(v) or v < 0 or v > 1 for v in target.values())
            or sum(target.values()) > 1 + 1e-12
        ):
            raise ValueError("INVALID_ACCOUNTING_WEIGHTS")
    cash, quantities, periods = 1.0, {p: 0.0 for p in products}, []
    fee = fee_bps / 10000
    for index, target in enumerate(targets):
        held = {p: quantities[p] * closes[p][index] for p in products}
        before = cash + sum(held.values())
        if not math.isfinite(before) or before <= 0:
            raise ValueError("INVALID_ACCOUNTING_EQUITY")
        desired = {p: target.get(p, 0.0) for p in products}
        unchanged = (
            sum(abs(desired[p] * before - held[p]) for p in products) <= 1e-12 * before
        )
        if decision_flags is not None and not decision_flags[index]:
            unchanged = True
        if unchanged:
            turnover, cost = 0.0, 0.0
        else:
            after = before
            if fee:
                lower, upper = 0.0, before
                for _ in range(80):
                    midpoint = (lower + upper) / 2
                    residual = (
                        midpoint
                        + fee
                        * sum(abs(desired[p] * midpoint - held[p]) for p in products)
                        - before
                    )
                    if residual > 0:
                        upper = midpoint
                    else:
                        lower = midpoint
                after = (lower + upper) / 2
            notionals = {p: desired[p] * after for p in products}
            traded = sum(abs(notionals[p] - held[p]) for p in products)
            cost, turnover = fee * traded, traded / before
            cash = before - cost - sum(notionals.values())
            if cash < -1e-12 * before:
                raise ValueError("UNFUNDED_ACCOUNTING_TRADE")
            cash = max(0.0, cash)
            quantities = {p: notionals[p] / closes[p][index] for p in products}
        marked = {p: quantities[p] * closes[p][index + 1] for p in products}
        equity = cash + sum(marked.values())
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("INVALID_ACCOUNTING_EQUITY")
        periods.append(
            {
                "date": dates[index + 1],
                "equity": equity,
                "cash": cash,
                "positions": marked,
                "weights": {p: marked[p] / equity for p in products},
                "turnover": turnover,
                "cost": cost,
                "net_return": equity / before - 1,
                "exposure": sum(marked.values()) / equity,
            }
        )
    return {
        "accounting_model": "self_financing_daily.v1",
        "quote_currency": quote_currency,
        "periods": periods,
    }


def summarize(net: dict, gross: dict, *, periods_per_year: int) -> dict:
    if (
        periods_per_year not in {252, 365}
        or not net["periods"]
        or len(net["periods"]) != len(gross["periods"])
    ):
        raise ValueError("INVALID_ACCOUNTING_SUMMARY")
    periods = net["periods"]
    returns = [p["net_return"] for p in periods]
    deviation = stdev(returns) if len(returns) > 1 else 0.0
    peak, drawdown = 1.0, 0.0
    for period in periods:
        peak = max(peak, period["equity"])
        drawdown = max(drawdown, 1 - period["equity"] / peak)
    net_return, gross_return = (
        periods[-1]["equity"] - 1,
        gross["periods"][-1]["equity"] - 1,
    )
    return {
        "periods": len(periods),
        "net_return": net_return,
        "gross_return": gross_return,
        "cost_drag": gross_return - net_return,
        "volatility": deviation * math.sqrt(periods_per_year),
        "sharpe": mean(returns) / deviation * math.sqrt(periods_per_year)
        if deviation
        else None,
        "max_drawdown": drawdown,
        "turnover": sum(p["turnover"] for p in periods),
        "total_costs": sum(p["cost"] for p in periods),
        "mean_daily_turnover": mean(p["turnover"] for p in periods),
        "mean_exposure": mean(p["exposure"] for p in periods),
        "flat_days": sum(
            p["exposure"] <= 1e-12 and p["turnover"] <= 1e-12 for p in periods
        ),
    }
