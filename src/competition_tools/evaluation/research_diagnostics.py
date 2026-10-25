"""Saved-output cost and descriptive PnL diagnostics, with no strategy replay."""

import math
from datetime import date


def number(value, *, minimum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError("INVALID_DIAGNOSTIC_NUMBER")
    return float(value)


def match(actual, expected):
    if not math.isclose(number(actual), number(expected), rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError("UNRECONCILED_DIAGNOSTIC")


def cost_threshold(period_returns):
    if not isinstance(period_returns, list) or not period_returns:
        raise ValueError("EMPTY_COST_DIAGNOSTIC")
    values = [number(r) for r in period_returns]
    if any(r <= -1 for r in values):
        raise ValueError("INVALID_COST_DIAGNOSTIC_RETURN")
    log_gross = math.fsum(math.log1p(r) for r in values)
    gross = math.expm1(log_gross)
    if not math.isfinite(gross):
        raise ValueError("NONFINITE_COST_DIAGNOSTIC")
    threshold = math.tanh(log_gross / (2 * len(values))) * 10000 if log_gross >= 0 else None
    return dict(dates=len(values), gross_return=gross, break_even_one_way_bps=threshold,
                positive_gross=log_gross > 0, accounting_model="daily_flat_cash_funded.v1")


def crypto_attribution(prices, account):
    if (not isinstance(prices, dict) or set(prices) != {"dates", "close"}
            or account.get("accounting_model") != "self_financing_daily.v1"
            or account.get("quote_currency") != "USDT"):
        raise ValueError("INVALID_ATTRIBUTION_IDENTITY")
    dates, closes, periods = prices["dates"], prices["close"], account.get("periods")
    if (not isinstance(dates, list) or len(dates) < 2 or dates != sorted(set(dates))
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
            or not isinstance(closes, dict) or not closes or not isinstance(periods, list)
            or len(periods) != len(dates) - 1):
        raise ValueError("INVALID_ATTRIBUTION_GRID")
    for values in closes.values():
        if not isinstance(values, list) or len(values) != len(dates) or any(number(v) <= 0 for v in values):
            raise ValueError("INVALID_ATTRIBUTION_PRICE")
    parts = {key: [] for key in ("market", "exposure", "selection", "cost")}
    previous, exposures, downside = 1.0, [], []
    for index, row in enumerate(periods):
        if row.get("date") != dates[index + 1] or set(row.get("positions", {})) != set(closes):
            raise ValueError("INVALID_ATTRIBUTION_PERIOD")
        returns = {p: closes[p][index + 1] / closes[p][index] - 1 for p in closes}
        market = math.fsum(returns.values()) / len(returns)
        end = {p: number(row["positions"][p], minimum=0) for p in closes}
        start = {p: end[p] / (1 + returns[p]) for p in closes}
        invested = math.fsum(start.values())
        equity, cash, cost = number(row["equity"]), number(row["cash"], minimum=0), number(row["cost"], minimum=0)
        if equity <= 0 or invested > previous + 1e-10:
            raise ValueError("INVALID_ATTRIBUTION_CAPITAL")
        match(cash + invested + cost, previous)
        match(cash + math.fsum(end.values()), equity)
        match(row["net_return"], equity / previous - 1)
        components = dict(market=previous * market, exposure=(invested - previous) * market,
                          selection=math.fsum(start[p] * (returns[p] - market) for p in closes), cost=-cost)
        match(math.fsum(components.values()), equity - previous)
        for key, value in components.items():
            parts[key].append(value)
        exposures.append(invested / previous)
        if market < 0:
            downside.append(dict(strategy_pnl=equity - previous, full_market_pnl=previous * market))
        previous = equity
    components = {key: math.fsum(values) for key, values in parts.items()}
    match(math.fsum(components.values()), previous - 1)
    return dict(schema="competition.crypto_attribution.v1", currency="USDT", causal=False,
                benchmark="frictionless_daily_equal_weight", components=components,
                net_return=previous - 1, dates=len(periods), mean_post_trade_exposure=math.fsum(exposures) / len(exposures),
                down_market_dates=len(downside), down_market_strategy_pnl=math.fsum(r["strategy_pnl"] for r in downside),
                down_market_full_reference_pnl=math.fsum(r["full_market_pnl"] for r in downside))
