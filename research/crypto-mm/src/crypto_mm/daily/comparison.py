"""Fixed holdings-policy and delayed-execution historical comparisons."""

from crypto_mm.portfolio.daily import build_control_targets
from crypto_mm.portfolio.rebalance import weekly_flags

from .study_accounting import account_periods, summarize

ARMS = ("buy_hold_equal_weight", "fixed60_weekly", "trend_weekly", "matched_weekly")
FEES = (0, 35, 50)
DELAYS = (0, 1)


def comparison_targets(bars, arm, delay):
    if arm not in ARMS or type(delay) is not int or delay not in DELAYS:
        raise ValueError("INVALID_COMPARISON_POLICY")
    trend = build_control_targets(bars, "trend200_vol40_strict")["targets"]
    products = sorted(bars["close"])
    dates = bars["dates"][251:-1]
    flags = weekly_flags(dates)
    if arm == "trend_weekly":
        targets = trend
    else:
        exposure = (
            [1.0] * len(trend)
            if arm == "buy_hold_equal_weight"
            else [0.6] * len(trend)
            if arm == "fixed60_weekly"
            else [sum(target.values()) for target in trend]
        )
        targets = [{p: value / len(products) for p in products} for value in exposure]
        if arm == "buy_hold_equal_weight":
            flags = [True] + [False] * (len(trend) - 1)
    if delay:
        targets, flags = [{}] + targets[:-1], [False] + flags[:-1]
    return targets, flags


def evaluate_comparison(bars, arm, fee_bps, delay):
    if type(fee_bps) is not int or fee_bps not in FEES:
        raise ValueError("INVALID_COMPARISON_COST")
    targets, flags = comparison_targets(bars, arm, delay)
    prices = dict(
        dates=bars["dates"][251:],
        close={p: rows[251:] for p, rows in bars["close"].items()},
    )
    net = account_periods(
        prices, targets, fee_bps=fee_bps, quote_currency="USDT", decision_flags=flags
    )
    gross = account_periods(
        prices, targets, fee_bps=0, quote_currency="USDT", decision_flags=flags
    )
    return dict(
        prices=prices,
        targets=targets,
        decision_flags=flags,
        net=net,
        gross=gross,
        metrics=summarize(net, gross, periods_per_year=365),
    )
