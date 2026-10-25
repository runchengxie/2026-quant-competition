"""Exact-session open rebalancing, held units, close marks and terminal sales."""

import math

from equity_lab.portfolio.cash_rebalance import rebalance


def replay_holdings(observations, calendar, dates, plans, *, horizon, fee_bps, delay):
    if (
        calendar != sorted(set(calendar))
        or dates != sorted(set(dates))
        or not dates
        or type(horizon) is not int
        or not 1 <= horizon <= 20
        or len(dates) % horizon
        or type(fee_bps) is not int
        or fee_bps not in (0, 20, 40)
        or type(delay) is not int
        or delay not in (0, 1)
    ):
        raise ValueError("INVALID_HOLDING_ACCOUNT")
    start = calendar.index(dates[0])
    if calendar[start : start + len(dates)] != dates or start + len(dates) + 1 >= len(
        calendar
    ):
        raise ValueError("INCOMPLETE_HOLDING_CALENDAR")
    if [row["date"] for row in plans] != dates[::horizon]:
        raise ValueError("INVALID_HOLDING_DECISIONS")
    scheduled = {calendar[calendar.index(p["date"]) + 1 + delay]: p for p in plans}
    valuation = calendar[start + 1 : start + len(dates) + 2]
    terminal = calendar[start + len(dates) + delay]
    cash, quantities, previous_close, previous, peak = 1.0, {}, {}, 1.0, 1.0
    periods, costs, turnovers, drawdown = [], [], [], 0.0
    reason, blocked_date = None, None
    for day in valuation:
        plan = scheduled.get(day)
        if plan is not None and plan.get("reason"):
            reason, blocked_date = plan["reason"], day
            break
        selected = plan["selected"] if plan is not None else []
        if plan is not None and (not selected or selected != sorted(set(selected))):
            raise ValueError("INVALID_HOLDING_SELECTED_NAMES")
        required = set(quantities) | set(selected)
        rows = {name: observations.get((day, name)) for name in required}
        if any(
            not row
            or row.get("valid") is not True
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
        opens, closes = ({n: rows[n][k] for n in required} for k in ("open", "close"))
        overnight = math.fsum(
            q * (opens[n] - previous_close[n]) for n, q in quantities.items()
        )
        trade_cost, traded = 0.0, 0.0
        if plan is not None:
            trade = rebalance(
                cash,
                quantities,
                opens,
                {n: 1 / len(selected) for n in selected},
                fee_bps,
            )
            cash, quantities, trade_cost, traded = (
                trade["cash"],
                trade["quantities"],
                trade["cost"],
                trade["traded"],
            )
        intraday = math.fsum(q * (closes[n] - opens[n]) for n, q in quantities.items())
        marked = {n: q * closes[n] for n, q in quantities.items()}
        liquidation_cost = 0.0
        if day == terminal:
            liquidation = rebalance(cash, quantities, closes, {}, fee_bps)
            cash, quantities = liquidation["cash"], liquidation["quantities"]
            liquidation_cost = liquidation["cost"]
            traded += liquidation["traded"]
            marked = {}
        cost = trade_cost + liquidation_cost
        equity = cash + math.fsum(marked.values())
        pnl = overnight + intraday
        if (
            not math.isfinite(equity)
            or equity <= 0
            or not math.isclose(
                equity - previous, pnl - cost, abs_tol=1e-10, rel_tol=1e-10
            )
        ):
            raise ValueError("UNRECONCILED_HOLDING_ACCOUNT")
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        turnover = traded / previous
        periods.append(
            dict(
                date=day,
                equity=equity,
                cash=cash,
                quantities=dict(quantities),
                positions=marked,
                trade_cost=trade_cost,
                liquidation_cost=liquidation_cost,
                cost=cost,
                price_pnl=pnl,
                turnover=turnover,
                net_return=equity / previous - 1,
            )
        )
        costs.append(cost)
        turnovers.append(turnover)
        previous, previous_close = equity, closes
    metrics = (
        dict(
            net_return=previous - 1,
            max_drawdown=drawdown,
            total_costs=math.fsum(costs),
            turnover=math.fsum(turnovers),
        )
        if reason is None
        else None
    )
    return dict(
        status="completed" if reason is None else "blocked",
        reason=reason,
        blocked_date=blocked_date,
        requested_dates=len(valuation),
        valid_dates=len(periods),
        metrics=metrics,
        periods=periods,
        accounting_model="raw_open_holding_cash.v1",
        currency="USD",
        formal_performance_ready=False,
    )
