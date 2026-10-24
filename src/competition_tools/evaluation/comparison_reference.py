"""Independent stdlib checks for fixed historical price/cost comparisons."""

import math
from datetime import date

from .contributions import explain_self_financing
from .robustness.reference import reference_account, reference_targets, compare_periods

EQUITY_ARMS = ("equal_weight", "reversal", "ridge", "elastic_net")
CRYPTO_ARMS = (
    "buy_hold_equal_weight",
    "fixed60_weekly",
    "trend_weekly",
    "matched_weekly",
)
METRICS = (
    "net_return",
    "gross_return",
    "cost_drag",
    "max_drawdown",
    "total_costs",
    "turnover",
    "top_asset_positive_price_pnl_share",
    "without_best_five_days_return",
)


def close(actual, expected):
    if (
        type(actual) not in (float, int)
        or not math.isfinite(actual)
        or not math.isclose(actual, expected, abs_tol=1e-10, rel_tol=1e-10)
    ):
        raise ValueError("COMPARISON_ARITHMETIC_MISMATCH")


def _identity(row, market):
    arms, fees = (
        (EQUITY_ARMS, (0, 20, 40)) if market == "equity" else (CRYPTO_ARMS, (0, 35, 50))
    )
    if (
        row["arm"] not in arms
        or type(row["fee_bps"]) is not int
        or row["fee_bps"] not in fees
        or type(row["delay"]) is not int
        or row["delay"] not in (0, 1)
    ):
        raise ValueError("INVALID_COMPARISON_IDENTITY")


def _concentration(contributions, returns):
    positive = math.fsum(max(0.0, value) for value in contributions.values())
    excluded = sorted(range(len(returns)), key=lambda i: (-returns[i], i))[:5]
    return dict(
        top_asset_positive_price_pnl_share=max(contributions.values()) / positive
        if positive
        else None,
        without_best_five_days_return=math.prod(
            1 + value for i, value in enumerate(returns) if i not in excluded
        )
        - 1,
    )


def rank_ic(predictions, targets):
    if len(predictions) != len(targets) or any(
        type(v) not in (int, float) or not math.isfinite(v)
        for v in [*predictions, *targets]
    ):
        raise ValueError("INVALID_RANK_INPUT")
    if len(predictions) < 30 or len(set(predictions)) < 2 or len(set(targets)) < 2:
        return None

    def ranks(values):
        ordered = sorted(range(len(values)), key=values.__getitem__)
        output = [0.0] * len(values)
        index = 0
        while index < len(ordered):
            end = index + 1
            while end < len(ordered) and values[ordered[end]] == values[ordered[index]]:
                end += 1
            for member in ordered[index:end]:
                output[member] = (index + 1 + end) / 2
            index = end
        return output

    left, right = ranks(predictions), ranks(targets)
    center = (len(left) + 1) / 2
    numerator = math.fsum(
        (x - center) * (y - center) for x, y in zip(left, right, strict=True)
    )
    denominator = math.sqrt(
        math.fsum((x - center) ** 2 for x in left)
        * math.fsum((y - center) ** 2 for y in right)
    )
    return numerator / denominator


def _chosen(pool, arm, scores, day):
    if not pool:
        return [], "EMPTY_DECISION_POOL"
    if arm == "equal_weight":
        return sorted(pool), None
    if scores is None and arm != "reversal":
        return [], "MODEL_UNAVAILABLE"
    values = {
        name: -value if arm == "reversal" else scores.get((day, name))
        for name, value in pool.items()
    }
    if any(
        type(v) not in (float, int) or not math.isfinite(v) for v in values.values()
    ):
        return [], "INVALID_SCORES"
    if len(set(values.values())) == 1:
        return [], "CONSTANT_SCORES"
    if len(values) < 50:
        return [], "INSUFFICIENT_DECISION_POOL"
    return sorted(sorted(values, key=lambda name: (-values[name], name))[:50]), None


def verify_equity_account(row, account, *, pool, observations, scores, sessions, dates):
    _identity(row, "equity")
    if (
        account.get("accounting_model") != "intraday_cash_proxy.v1"
        or account.get("quote_currency") != "USD"
        or account.get("pnl_available") is not False
        or account.get("ex_post_diagnostic") is not True
        or account.get("requested_dates") != len(dates)
        or len(account.get("periods", [])) != len(dates)
    ):
        raise ValueError("INVALID_EQUITY_COMPARISON_MODEL")
    fee, nav, gross, peak, drawdown = row["fee_bps"] / 10000, 1.0, 1.0, 1.0, 0.0
    continuous, valid, costs, turnover = True, 0, [], 0.0
    contributions, returns = {}, []
    for day, actual in zip(dates, account["periods"], strict=True):
        selected, reason = _chosen(pool.get(day, {}), row["arm"], scores, day)
        index = sessions.index(day) + 1 + row["delay"]
        execution = sessions[index] if index < len(sessions) else None
        if (
            actual.get("date") != day
            or actual.get("execution_date") != execution
            or actual.get("selected") != selected
        ):
            raise ValueError("COMPARISON_SELECTION_OR_CALENDAR_CHANGED")
        changes = [observations.get((execution, name)) for name in selected]
        if reason is None and execution is None:
            reason = "MISSING_EXECUTION_SESSION"
        elif reason is None and any(v is None for v in changes):
            reason = "MISSING_SELECTED_OUTCOME"
        if reason:
            if actual.get("status") != "blocked" or actual.get("reason") != reason:
                raise ValueError("COMPARISON_MISSINGNESS_CHANGED")
            continuous = False
            continue
        if any(
            type(v) not in (float, int) or not math.isfinite(v) or v <= -1
            for v in changes
        ):
            raise ValueError("INVALID_COMPARISON_RETURN")
        change = math.fsum(changes) / len(selected)
        factor = (1 + change) * (1 - fee) / (1 + fee)
        if actual.get("status") != "completed" or actual.get("reason") is not None:
            raise ValueError("COMPARISON_UNEXPECTED_BLOCK")
        close(actual.get("net_return"), factor - 1)
        valid += 1
        if not continuous:
            if any(
                actual.get(key) is not None for key in ("equity", "price_pnl", "cost")
            ):
                raise ValueError("COMPARISON_COMPOUNDED_ACROSS_GAP")
            continue
        price_pnl, cost = nav * change / (1 + fee), nav * fee * (2 + change) / (1 + fee)
        for name, value in zip(selected, changes, strict=True):
            contributions[name] = contributions.get(name, 0.0) + nav * value / len(
                selected
            ) / (1 + fee)
        nav, gross = nav * factor, gross * (1 + change)
        for key, expected in (
            ("equity", nav),
            ("price_pnl", price_pnl),
            ("cost", cost),
        ):
            close(actual.get(key), expected)
        costs.append(cost)
        returns.append(factor - 1)
        turnover += (2 + change) / (1 + fee)
        peak = max(peak, nav)
        drawdown = max(drawdown, 1 - nav / peak)
    if account.get("valid_dates") != valid or account.get("status") != (
        "completed" if continuous else "blocked"
    ):
        raise ValueError("COMPARISON_COVERAGE_CHANGED")
    if not continuous:
        if account.get("metrics") is not None:
            raise ValueError("COMPARISON_METRICS_ACROSS_GAP")
        return None
    expected = dict(
        net_return=nav - 1,
        gross_return=gross - 1,
        cost_drag=gross - nav,
        max_drawdown=drawdown,
        total_costs=math.fsum(costs),
        turnover=turnover,
        **_concentration(contributions, returns),
    )
    if set(account.get("metrics", {})) != set(METRICS):
        raise ValueError("INVALID_COMPARISON_METRICS")
    for key, value in expected.items():
        if value is None:
            if account["metrics"][key] is not None:
                raise ValueError("COMPARISON_NULL_CHANGED")
        else:
            close(account["metrics"][key], value)
    return expected


def verify_crypto_account(row, account, bars):
    _identity(row, "crypto")
    dates, prices = bars["dates"], bars["close"]
    if (
        len(dates) != 342
        or dates != sorted(set(dates))
        or not prices
        or any(
            len(values) != len(dates)
            or any(
                type(v) not in (float, int) or not math.isfinite(v) or v <= 0
                for v in values
            )
            for values in prices.values()
        )
    ):
        raise ValueError("INVALID_COMPARISON_SOURCE")
    expected_prices = dict(
        dates=dates[251:], close={p: values[251:] for p, values in prices.items()}
    )
    if account.get("prices") != expected_prices:
        raise ValueError("COMPARISON_PRICE_SOURCE_CHANGED")
    products = sorted(prices)
    trend = reference_targets(
        dict(market="crypto", input_job=dict(arm_id="trend200_vol40_strict")), bars
    )
    flags = [
        i == 0 or date.fromisoformat(day).weekday() == 0
        for i, day in enumerate(dates[251:-1])
    ]
    if row["arm"] == "trend_weekly":
        targets = trend
    else:
        exposures = [
            1.0
            if row["arm"] == "buy_hold_equal_weight"
            else 0.6
            if row["arm"] == "fixed60_weekly"
            else sum(t.values())
            for t in trend
        ]
        targets = [
            {p: exposure / len(products) for p in products} for exposure in exposures
        ]
        if row["arm"] == "buy_hold_equal_weight":
            flags = [True] + [False] * 89
    if row["delay"]:
        targets, flags = [{}] + targets[:-1], [False] + flags[:-1]
    if account.get("decision_flags") != flags or len(account.get("targets", [])) != 90:
        raise ValueError("COMPARISON_POLICY_CHANGED")
    for expected, actual in zip(targets, account["targets"], strict=True):
        if set(actual) != set(expected):
            raise ValueError("COMPARISON_TARGET_CHANGED")
        for product, weight in expected.items():
            close(actual[product], weight)
    for name, fee in (("net", row["fee_bps"]), ("gross", 0)):
        compare_periods(
            reference_account(
                expected_prices, targets, fee_bps=fee, decision_flags=flags
            ),
            account[name]["periods"],
        )
    explanation = explain_self_financing(
        expected_prices, account["net"], account["gross"]
    )
    periods = account["net"]["periods"]
    peak, drawdown = 1.0, 0.0
    for period in periods:
        peak = max(peak, period["equity"])
        drawdown = max(drawdown, 1 - period["equity"] / peak)
    expected = dict(
        net_return=explanation["net_return"],
        gross_return=account["gross"]["periods"][-1]["equity"] - 1,
        cost_drag=explanation["counterfactual_cost_drag_return"],
        max_drawdown=drawdown,
        total_costs=explanation["modeled_costs"],
        turnover=math.fsum(p["turnover"] for p in periods),
    )
    for key, value in expected.items():
        close(account["metrics"][key], value)
    return expected | _concentration(
        {r["instrument"]: r["price_pnl"] for r in explanation["instruments"]},
        [p["net_return"] for p in periods],
    )
