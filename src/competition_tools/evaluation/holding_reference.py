"""Independent stdlib selection and piecewise-linear holdings verification."""

import math

from .research_diagnostics import match, number


def verify_plans(plans, pool, predictions, dates, horizon, arm, buffer):
    if [p["date"] for p in plans] != dates[::horizon]:
        raise ValueError("HOLDING_DECISION_GRID_CHANGED")
    previous = []
    for day, actual in zip(dates[::horizon], plans, strict=True):
        current = {name: row for name, row in pool.get(day, {}).items() if row["valid"]}
        chosen, reason = [], None
        if not current:
            reason = "EMPTY_DECISION_POOL"
        elif arm == "equal_weight":
            chosen = sorted(current)
        elif arm != "reversal" and predictions is None:
            reason = "MODEL_UNAVAILABLE"
        else:
            scores = {
                n: -r["session_return"]
                if arm == "reversal"
                else predictions.get((day, n))
                for n, r in current.items()
            }
            if len(scores) < 50 or any(
                type(v) not in (int, float) or not math.isfinite(v)
                for v in scores.values()
            ):
                reason = "INVALID_RANKING_POOL"
            elif len(set(scores.values())) == 1:
                reason = "CONSTANT_SCORES"
            else:
                ordered = sorted(scores, key=lambda name: (-scores[name], name))
                keep = set(previous) & set(ordered[: 50 + buffer])
                chosen = [n for n in ordered if n in keep][:50]
                chosen += [n for n in ordered if n not in keep][: 50 - len(chosen)]
                chosen.sort()
        if actual != dict(date=day, selected=chosen, reason=reason):
            raise ValueError("HOLDING_SELECTION_CHANGED")
        if reason is None:
            previous = chosen


def _fund(cash, quantities, prices, targets, fee):
    names = sorted(set(quantities) | set(targets))
    held = {name: quantities.get(name, 0) * prices[name] for name in names}
    before = cash + math.fsum(held.values())
    if (
        math.fsum(abs(targets.get(n, 0) * before - held[n]) for n in names)
        <= 1e-12 * before
    ):
        return cash, dict(quantities), 0.0, 0.0
    points = sorted(
        {
            0.0,
            before,
            *(
                held[n] / targets[n]
                for n in names
                if targets.get(n, 0) > 0 and 0 < held[n] / targets[n] < before
            ),
        }
    )
    funded = None
    for lower, upper in zip(points, points[1:]):
        middle = (lower + upper) / 2
        signs = {n: 1 if targets.get(n, 0) * middle >= held[n] else -1 for n in names}
        proposed = (before + fee * math.fsum(signs[n] * held[n] for n in names)) / (
            1 + fee * math.fsum(signs[n] * targets.get(n, 0) for n in names)
        )
        if lower - 1e-12 <= proposed <= upper + 1e-12:
            funded = proposed
            break
    if funded is None or funded <= 0:
        raise ValueError("INDEPENDENT_FUNDING_UNSOLVED")
    traded = math.fsum(abs(targets.get(n, 0) * funded - held[n]) for n in names)
    cost = traded * fee
    return (
        max(0.0, before - cost - sum(targets.values()) * funded),
        {n: w * funded / prices[n] for n, w in targets.items() if w > 0},
        cost,
        traded,
    )


def _values(actual, expected):
    if not isinstance(actual, dict) or set(actual) != set(expected):
        raise ValueError("HOLDING_PERIOD_FIELDS_CHANGED")
    for key, value in expected.items():
        if isinstance(value, dict):
            _values(actual[key], value)
        elif isinstance(value, str):
            if actual[key] != value:
                raise ValueError("HOLDING_PERIOD_DATE_CHANGED")
        else:
            match(actual[key], value)


def verify_holding_account(
    actual, observations, calendar, dates, plans, *, horizon, fee_bps, delay
):
    if (
        actual.get("accounting_model") != "raw_open_holding_cash.v1"
        or actual.get("currency") != "USD"
        or actual.get("formal_performance_ready") is not False
    ):
        raise ValueError("INVALID_HOLDING_IDENTITY")
    first = calendar.index(dates[0])
    valuation = calendar[first + 1 : first + len(dates) + 2]
    scheduled = {calendar[calendar.index(p["date"]) + 1 + delay]: p for p in plans}
    terminal = calendar[first + len(dates) + delay]
    if (
        len(valuation) != len(dates) + 1
        or [p["date"] for p in plans] != dates[::horizon]
    ):
        raise ValueError("INVALID_HOLDING_CALENDAR")
    fee, cash, quantities, previous_prices, previous, peak = (
        fee_bps / 10000,
        1.0,
        {},
        {},
        1.0,
        1.0,
    )
    expected, reason, blocked_date, max_drawdown = [], None, None, 0.0
    for day in valuation:
        plan = scheduled.get(day)
        if plan and plan["reason"]:
            reason, blocked_date = plan["reason"], day
            break
        selected = plan["selected"] if plan else []
        needed = set(quantities) | set(selected)
        rows = {name: observations.get((day, name)) for name in needed}
        if any(
            row is None
            or row["valid"] is not True
            or any(
                type(row.get(k)) not in (int, float)
                or not math.isfinite(row[k])
                or row[k] <= 0
                for k in ("open", "close")
            )
            for row in rows.values()
        ):
            reason, blocked_date = "MISSING_HELD_OR_SELECTED_PRICE", day
            break
        if any(row.get("action_boundary", False) for row in rows.values()):
            reason, blocked_date = "KNOWN_ACTION_BOUNDARY", day
            break
        opens, closes = ({n: rows[n][key] for n in needed} for key in ("open", "close"))
        before_trade = dict(quantities)
        overnight = math.fsum(
            q * (opens[n] - previous_prices[n]) for n, q in before_trade.items()
        )
        trade_cost, traded = 0.0, 0.0
        if plan:
            cash, quantities, trade_cost, traded = _fund(
                cash, quantities, opens, {n: 1 / len(selected) for n in selected}, fee
            )
        intraday = math.fsum(q * (closes[n] - opens[n]) for n, q in quantities.items())
        positions = {n: q * closes[n] for n, q in quantities.items()}
        liquidation_cost = 0.0
        if day == terminal:
            liquidation_notional = math.fsum(positions.values())
            liquidation_cost = liquidation_notional * fee
            cash += liquidation_notional - liquidation_cost
            quantities, positions = {}, {}
            traded += liquidation_notional
        cost = trade_cost + liquidation_cost
        equity = cash + math.fsum(positions.values())
        number(equity, minimum=1e-100)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, 1 - equity / peak)
        expected.append(
            dict(
                date=day,
                equity=equity,
                cash=cash,
                quantities=dict(quantities),
                positions=positions,
                trade_cost=trade_cost,
                liquidation_cost=liquidation_cost,
                cost=cost,
                price_pnl=overnight + intraday,
                turnover=traded / previous,
                net_return=equity / previous - 1,
            )
        )
        previous, previous_prices = equity, closes
    if (
        actual.get("status") != ("completed" if reason is None else "blocked")
        or actual.get("reason") != reason
        or actual.get("blocked_date") != blocked_date
        or actual.get("requested_dates") != len(valuation)
        or actual.get("valid_dates") != len(expected)
        or len(actual.get("periods", [])) != len(expected)
    ):
        raise ValueError("HOLDING_COVERAGE_CHANGED")
    for row, reference in zip(actual["periods"], expected, strict=True):
        _values(row, reference)
    if reason is None:
        _values(
            actual["metrics"],
            dict(
                net_return=previous - 1,
                max_drawdown=max_drawdown,
                total_costs=math.fsum(r["cost"] for r in expected),
                turnover=math.fsum(r["turnover"] for r in expected),
            ),
        )
    elif actual.get("metrics") is not None:
        raise ValueError("BLOCKED_HOLDING_HAS_METRICS")
    return actual["metrics"]
