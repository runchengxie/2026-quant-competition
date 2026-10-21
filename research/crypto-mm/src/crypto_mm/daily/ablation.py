"""Fixed unlevered trend overlays, independent of maker event simulation."""

import math
from statistics import stdev
from .study_accounting import account_periods, summarize, validate_prices
from .study import evaluate_study


def hysteresis_states(prices):
    active = False
    states = []
    for i, close in enumerate(prices):
        if i >= 199:
            average = sum(prices[i - 199 : i + 1]) / 200
            if close > 1.02 * average:
                active = True
            elif close < 0.98 * average:
                active = False
        states.append(active)
    return states


def build_targets(bars: dict, strategy: str, variant_id: str) -> dict:
    if strategy != "trend_200d" or variant_id not in {
        "hysteresis_2pct",
        "vol_target_40pct",
        "fixed_exposure_60pct",
    }:
        raise ValueError("INVALID_CRYPTO_ABLATION")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20:
        raise ValueError("INVALID_STUDY_PRICES")
    states = (
        {p: hysteresis_states(closes[p]) for p in products}
        if variant_id == "hysteresis_2pct"
        else {}
    )
    targets = []
    for index in range(252, len(dates)):
        decision = index - 1
        selected = (
            [p for p in products if states[p][decision]]
            if states
            else [
                p
                for p in products
                if closes[p][decision]
                > sum(closes[p][decision - 199 : decision + 1]) / 200
            ]
        )
        scale = 0.6 if variant_id == "fixed_exposure_60pct" else 1.0
        if variant_id == "vol_target_40pct" and selected:
            observed = [
                sum(closes[p][j] / closes[p][j - 1] - 1 for p in selected)
                / len(selected)
                for j in range(decision - 19, decision + 1)
            ]
            volatility = stdev(observed) * math.sqrt(365)
            if not math.isfinite(volatility):
                raise ValueError("INVALID_ABLATION_VOLATILITY")
            scale = min(1.0, 0.4 / volatility) if volatility > 0 else 1.0
        targets.append({p: scale / len(selected) for p in selected} if selected else {})
    return {"targets": targets, "decision_flags": [True] * len(targets)}


def evaluate_ablation(
    bars: dict, strategy: str, variant_id: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if variant_id == "baseline":
        return evaluate_study(
            bars, strategy, fee_bps=fee_bps, quote_currency=quote_currency
        )
    if quote_currency != "USDT":
        raise ValueError("INVALID_CRYPTO_ABLATION")
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
    return {
        "net": net,
        "gross": gross,
        "metrics": summarize(net, gross, periods_per_year=365),
    }
