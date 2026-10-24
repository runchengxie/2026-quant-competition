"""Fixed crypto daily study; event-driven maker simulation remains separate."""

from .study_accounting import account_periods, summarize
from crypto_mm.portfolio.daily import build_study_targets


def evaluate_study(
    bars: dict, strategy: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if (
        strategy not in {"equal_weight", "momentum_63d", "trend_200d"}
        or quote_currency != "USDT"
    ):
        raise ValueError("INVALID_CRYPTO_STUDY")
    targets = build_study_targets(bars, strategy)
    dates, closes = bars["dates"], bars["close"]
    scored = {"dates": dates[251:], "close": {p: v[251:] for p, v in closes.items()}}
    net = account_periods(
        scored, targets, fee_bps=fee_bps, quote_currency=quote_currency
    )
    gross = account_periods(scored, targets, fee_bps=0, quote_currency=quote_currency)
    return {
        "net": net,
        "gross": gross,
        "metrics": summarize(net, gross, periods_per_year=365),
    }
