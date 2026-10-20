"""Lagged, long-only daily baselines with explicit costs and quote units."""

import math
from datetime import date
from statistics import mean, stdev


def evaluate(bars: dict, strategy: str, *, fee_bps: float) -> dict:
    if strategy not in {"equal_weight", "momentum_63d"}:
        raise ValueError("UNKNOWN_DAILY_STRATEGY")
    if bars["quote_currency"] != "USDT" or bars["calendar"] != "365":
        raise ValueError("INCOMPATIBLE_DAILY_IDENTITY")
    if not math.isfinite(fee_bps) or not 0 <= fee_bps <= 100:
        raise ValueError("INVALID_FEE")
    dates, prices = bars["dates"], bars["close"]
    if len(dates) < 64:
        raise ValueError("INSUFFICIENT_HISTORY")
    if dates != sorted(set(dates)) or not prices:
        raise ValueError("INVALID_DAILY_GRID")
    for earlier, later in zip(dates, dates[1:]):
        if (date.fromisoformat(later) - date.fromisoformat(earlier)).days != 1:
            raise ValueError("NONCONTIGUOUS_DAILY_GRID")
    products = sorted(prices)
    if any(not p.endswith("USDT") for p in products):
        raise ValueError("MIXED_QUOTE_CURRENCY")
    if any(
        len(values) != len(dates) or any(not math.isfinite(v) or v <= 0 for v in values)
        for values in prices.values()
    ):
        raise ValueError("INVALID_DAILY_PRICES")
    held = {p: 0.0 for p in products}
    equity, gross_equity, peak, max_drawdown, total_turnover = 1.0, 1.0, 1.0, 0.0, 0.0
    periods = []
    for index in range(63, len(dates)):
        if strategy == "equal_weight":
            target = (
                {p: 1 / len(products) for p in products} if index == 63 else held.copy()
            )
        else:
            # index-1 is the latest known close before this holding period.
            selected = [
                p
                for p in products
                if index >= 64 and prices[p][index - 1] > prices[p][index - 64]
            ]
            target = {
                p: (1 / len(selected) if p in selected else 0.0) for p in products
            }
        turnover = sum(abs(target[p] - held[p]) for p in products)
        cost = turnover * fee_bps / 10_000
        returns = {p: prices[p][index] / prices[p][index - 1] - 1 for p in products}
        gross = sum(target[p] * returns[p] for p in products)
        net = (1 - cost) * (1 + gross) - 1
        equity *= 1 + net
        gross_equity *= 1 + gross
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, 1 - equity / peak)
        total_turnover += turnover
        periods.append(
            {
                "date": dates[index],
                "weights": target.copy(),
                "exposure": sum(target.values()),
                "gross_return": gross,
                "net_return": net,
                "turnover": turnover,
                "cost_fraction": cost,
                "equity": equity,
            }
        )
        held = {p: target[p] * (1 + returns[p]) / (1 + gross) for p in products}
    net_returns = [p["net_return"] for p in periods]
    volatility = stdev(net_returns) if len(net_returns) > 1 else 0.0
    return {
        "schema": "competition.crypto_daily_result.v1",
        "strategy": strategy,
        "quote_currency": "USDT",
        "periods_per_year": 365,
        "fee_bps": fee_bps,
        "warmup_days": 63,
        "signal_lag_periods": 1,
        "retrospective": True,
        "start": periods[0]["date"],
        "end": periods[-1]["date"],
        "products": products,
        "net_return": equity - 1,
        "gross_return": gross_equity - 1,
        "sharpe": mean(net_returns) / volatility * math.sqrt(365)
        if volatility
        else None,
        "max_drawdown": max_drawdown,
        "turnover": total_turnover,
        "mean_exposure": mean(p["exposure"] for p in periods),
        "periods": periods,
        "accepted_research": False,
    }
