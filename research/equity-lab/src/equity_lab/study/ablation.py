"""Fixed calendar decisions using lagged signals and held-share drift."""

from datetime import date
import pandas as pd
from ..signals.momentum import generate_momentum_signal
from ..signals.sma import generate_sma_signal
from .accounting import account_periods, summarize, validate_prices
from .run import evaluate_study


def build_targets(bars: dict, strategy: str, variant_id: str) -> dict:
    if strategy not in {
        "equal_weight",
        "momentum_20d",
        "sma_cross",
    } or variant_id not in {"weekly", "monthly"}:
        raise ValueError("INVALID_EQUITY_ABLATION")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20:
        raise ValueError("INVALID_STUDY_PRICES")
    signals = {}
    if strategy != "equal_weight":
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
        signals = {(r.code, r.date): int(r.signal) for r in frame.itertuples()}
    quantities = {}
    targets = []
    flags = []
    for index in range(252, len(dates)):
        decision = index - 1
        day = date.fromisoformat(dates[decision])
        prior = date.fromisoformat(dates[decision - 1])
        rebalance = index == 252 or (
            day.isocalendar()[:2] != prior.isocalendar()[:2]
            if variant_id == "weekly"
            else (day.year, day.month) != (prior.year, prior.month)
        )
        if rebalance:
            selected = (
                products[:10]
                if strategy == "equal_weight"
                else [p for p in products if signals[(p, dates[decision])] > 0][:10]
            )
            target = {p: 1 / len(selected) for p in selected} if selected else {}
            quantities = {p: target[p] / closes[p][decision] for p in target}
        else:
            # Fully invested/cash schedules: fees scale all shares equally.
            values = {p: q * closes[p][decision] for p, q in quantities.items()}
            total = sum(values.values())
            target = {p: v / total for p, v in values.items()} if total else {}
        targets.append(target)
        flags.append(rebalance)
    return {"targets": targets, "decision_flags": flags}


def evaluate_ablation(
    bars: dict, strategy: str, variant_id: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if variant_id == "baseline":
        return evaluate_study(
            bars, strategy, fee_bps=fee_bps, quote_currency=quote_currency
        )
    if quote_currency not in {"USD", "HKD"}:
        raise ValueError("INVALID_EQUITY_ABLATION")
    generated = build_targets(bars, strategy, variant_id)
    scored = {
        "dates": bars["dates"][251:],
        "close": {p: v[251:] for p, v in bars["close"].items()},
    }
    net = account_periods(
        scored, generated["targets"], fee_bps=fee_bps, quote_currency=quote_currency
    )
    gross = account_periods(
        scored, generated["targets"], fee_bps=0, quote_currency=quote_currency
    )
    if any(
        not flag and p["turnover"] != 0
        for flag, p in zip(generated["decision_flags"], net["periods"])
    ):
        raise ValueError("OFF_SCHEDULE_TRADE")
    return {
        "net": net,
        "gross": gross,
        "metrics": summarize(net, gross, periods_per_year=252),
    }
