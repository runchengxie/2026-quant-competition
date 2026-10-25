"""Long-only fractional units with cash-funded proportional transaction fees."""

import math


def rebalance(cash, quantities, prices, target, fee_bps):
    def valid(value):
        return type(value) in (int, float) and math.isfinite(value)

    if (
        not valid(cash)
        or cash < -1e-12
        or not valid(fee_bps)
        or not 0 <= fee_bps <= 100
        or not all(isinstance(v, dict) for v in (quantities, prices, target))
        or not set(quantities) | set(target) <= set(prices)
        or any(not valid(v) or v <= 0 for v in prices.values())
        or any(not valid(v) or v < 0 for v in quantities.values())
        or any(not valid(v) or not 0 <= v <= 1 for v in target.values())
        or sum(target.values()) > 1 + 1e-12
    ):
        raise ValueError("INVALID_CASH_REBALANCE")
    names = sorted(set(quantities) | set(target))
    held = {name: quantities.get(name, 0) * prices[name] for name in names}
    before = cash + math.fsum(held.values())
    if before <= 0 or not math.isfinite(before):
        raise ValueError("INVALID_ACCOUNT_EQUITY")
    if (
        math.fsum(abs(target.get(n, 0) * before - held[n]) for n in names)
        <= 1e-12 * before
    ):
        return dict(
            cash=cash, quantities=dict(quantities), cost=0.0, traded=0.0, before=before
        )
    fee = fee_bps / 10000
    lower, upper = 0.0, before
    for _ in range(80):
        after = (lower + upper) / 2
        cost = fee * math.fsum(abs(target.get(n, 0) * after - held[n]) for n in names)
        if after + cost > before:
            upper = after
        else:
            lower = after
    after = (lower + upper) / 2
    notionals = {name: target.get(name, 0) * after for name in names}
    traded = math.fsum(abs(notionals[n] - held[n]) for n in names)
    cost = traded * fee
    cash = before - cost - math.fsum(notionals.values())
    if cash < -1e-11 * before:
        raise ValueError("UNFUNDED_HOLDING_TRADE")
    return dict(
        cash=max(0.0, cash),
        quantities={n: v / prices[n] for n, v in notionals.items() if v > 0},
        cost=cost,
        traded=traded,
        before=before,
    )
