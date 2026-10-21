"""Fixed crypto daily study; event-driven maker simulation remains separate."""

from .study_accounting import account_periods, summarize, validate_prices


def evaluate_study(
    bars: dict, strategy: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if (
        strategy not in {"equal_weight", "momentum_63d", "trend_200d"}
        or quote_currency != "USDT"
    ):
        raise ValueError("INVALID_CRYPTO_STUDY")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253 or not closes:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20 or any(len(v) != len(dates) for v in closes.values()):
        raise ValueError("INVALID_STUDY_PRICES")
    quantities = {p: 1 / len(products) / closes[p][251] for p in products}
    targets = []
    for index in range(252, len(dates)):
        decision = index - 1
        if strategy == "equal_weight":
            values = {p: q * closes[p][decision] for p, q in quantities.items()}
            target = {p: v / sum(values.values()) for p, v in values.items()}
        else:
            selected = (
                [p for p in products if closes[p][decision] > closes[p][decision - 63]]
                if strategy == "momentum_63d"
                else [
                    p
                    for p in products
                    if closes[p][decision]
                    > sum(closes[p][decision - 199 : decision + 1]) / 200
                ]
            )
            target = {p: 1 / len(selected) for p in selected} if selected else {}
        targets.append(target)
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
