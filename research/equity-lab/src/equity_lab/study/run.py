"""Fixed equity signal comparisons using the explicit optional accounting path."""

import pandas as pd

from ..signals.momentum import generate_momentum_signal
from ..signals.sma import generate_sma_signal
from .accounting import account_periods, summarize, validate_prices


def evaluate_study(
    bars: dict, strategy: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if strategy not in {
        "buy_hold",
        "benchmark_buy_hold",
        "equal_weight",
        "momentum_20d",
        "sma_cross",
    } or quote_currency not in {"USD", "HKD"}:
        raise ValueError("INVALID_EQUITY_STUDY")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253 or not closes:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20 or any(len(v) != len(dates) for v in closes.values()):
        raise ValueError("INVALID_STUDY_PRICES")
    signals = {}
    if strategy in {"momentum_20d", "sma_cross"}:
        frame = pd.DataFrame(
            [
                {"code": p, "date": d, "close": closes[p][i]}
                for p in products
                for i, d in enumerate(dates)
            ]
        )
        frame = (
            generate_momentum_signal(frame, lookback_days=20, min_momentum=0)
            if strategy == "momentum_20d"
            else generate_sma_signal(frame, short_window=20, long_window=60)
        )
        signals = {(row.code, row.date): int(row.signal) for row in frame.itertuples()}
    initial = products[:10]
    quantities = {p: 1 / len(initial) / closes[p][251] for p in initial}
    targets = []
    for index in range(252, len(dates)):
        decision = index - 1
        if strategy in {"buy_hold", "benchmark_buy_hold"}:
            values = {p: q * closes[p][decision] for p, q in quantities.items()}
            total = sum(values.values())
            target = {p: v / total for p, v in values.items()}
        else:
            selected = (
                products[:10]
                if strategy == "equal_weight"
                else [p for p in products if signals[(p, dates[decision])] > 0][:10]
            )
            target = {p: 1 / len(selected) for p in selected} if selected else {}
        targets.append(target)
    scored = {
        "dates": dates[251:],
        "close": {p: values[251:] for p, values in closes.items()},
    }
    net = account_periods(
        scored, targets, fee_bps=fee_bps, quote_currency=quote_currency
    )
    gross = account_periods(scored, targets, fee_bps=0, quote_currency=quote_currency)
    return {
        "net": net,
        "gross": gross,
        "metrics": summarize(net, gross, periods_per_year=252),
    }
