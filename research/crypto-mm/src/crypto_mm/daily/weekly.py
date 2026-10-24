"""Fixed weekly trend and distinct calendar/exposure controls."""

from crypto_mm.portfolio.rebalance import weekly_flags as weekly_flags

from .controls import build_control_targets
from .study_accounting import account_periods, summarize

ARMS = (
    "daily_trend",
    "daily_matched",
    "weekly_trend",
    "weekly_calendar_matched",
    "weekly_exposure_matched",
)


def _exposures(account, targets, flags):
    # Previous marked period ends at the current decision close. It is known
    # before this day's trade and before the next price return.
    return [
        sum(target.values()) if flag else account["periods"][i - 1]["exposure"]
        for i, (target, flag) in enumerate(zip(targets, flags))
    ]


def _accounts(bars, fee_bps):
    targets = build_control_targets(bars, "trend200_vol40_strict")["targets"]
    prices = {
        "dates": bars["dates"][251:],
        "close": {p: rows[251:] for p, rows in bars["close"].items()},
    }
    products = sorted(prices["close"])
    daily = [True] * len(targets)
    weekly = weekly_flags(prices["dates"][:-1])
    output = {}

    def equal_weights(exposures):
        return [{p: value / len(products) for p in products} for value in exposures]

    def run(name, weights, flags):
        account = account_periods(
            prices,
            weights,
            fee_bps=fee_bps,
            quote_currency="USDT",
            decision_flags=flags,
        )
        exposure = _exposures(account, weights, flags)
        output[name] = {
            "account": account,
            "decision_exposure": exposure,
            "decision_flags": flags,
            "scheduled_rebalances": sum(flags),
            "actual_rebalances": sum(p["turnover"] > 1e-12 for p in account["periods"]),
        }
        return exposure

    daily_exposure = run("daily_trend", targets, daily)
    run("daily_matched", equal_weights(daily_exposure), daily)
    weekly_exposure = run("weekly_trend", targets, weekly)
    run(
        "weekly_calendar_matched",
        equal_weights([sum(t.values()) for t in targets]),
        weekly,
    )
    run("weekly_exposure_matched", equal_weights(weekly_exposure), daily)
    return output


def evaluate_weekly(bars, fee_bps):
    if type(fee_bps) is not int or fee_bps not in (35, 50):
        raise ValueError("INVALID_WEEKLY_COST")
    net = _accounts(bars, fee_bps)
    gross = _accounts(bars, 0)
    return {
        name: {
            "net": net[name]["account"],
            "gross": gross[name]["account"],
            "metrics": summarize(
                net[name]["account"], gross[name]["account"], periods_per_year=365
            ),
            "decision_exposure": net[name]["decision_exposure"],
            "decision_flags": net[name]["decision_flags"],
            "scheduled_rebalances": net[name]["scheduled_rebalances"],
            "actual_rebalances": net[name]["actual_rebalances"],
        }
        for name in ARMS
    }
