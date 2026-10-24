"""Replay the fixed daily ablation policies; preserve existing public helpers."""

from crypto_mm.portfolio.daily import build_ablation_targets as build_targets
from crypto_mm.signals.daily_trend import hysteresis_states as hysteresis_states
from .study_accounting import account_periods, summarize
from .study import evaluate_study


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
