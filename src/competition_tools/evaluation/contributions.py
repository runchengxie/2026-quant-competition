"""Reconcile model price contributions and costs from file-contract artifacts."""

import math
from datetime import date

CURRENCIES = {"USD", "HKD", "USDT"}
TOLERANCE = 1e-10


def _number(value, *, minimum=None):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (minimum is not None and value < minimum)
    ):
        raise ValueError("INVALID_CONTRIBUTION_NUMBER")
    return float(value)


def _sum(values):
    try:
        return _number(math.fsum(_number(v) for v in values))
    except (OverflowError, ArithmeticError) as error:
        raise ValueError("NONFINITE_CONTRIBUTION_SUM") from error


def _match(actual, expected, *scale):
    actual, expected = _number(actual), _number(expected)
    difference = abs(actual - expected)
    if difference > TOLERANCE * max([1.0, *(abs(v) for v in scale)]):
        raise ValueError("UNRECONCILED_CONTRIBUTION")
    return difference


def _dates(values):
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(v, str) for v in values)
    ):
        raise ValueError("INVALID_CONTRIBUTION_DATES")
    try:
        valid = values == sorted(set(values)) and all(
            date.fromisoformat(v).isoformat() == v for v in values
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("INVALID_CONTRIBUTION_DATES")
    return values


def _report(
    model, currency, initial, final, gross_final, contributions, costs, errors, periods
):
    price_pnl = _sum(contributions.values())
    net_pnl = _number(final - initial)
    errors.append(_match(price_pnl - costs, net_pnl, initial, final))
    return dict(
        schema="competition.performance_explanation.v1",
        accounting_model=model,
        quote_currency=currency,
        initial_equity=initial,
        final_equity=final,
        instruments=[
            dict(instrument=p, price_pnl=v, return_contribution=_number(v / initial))
            for p, v in sorted(contributions.items())
        ],
        price_pnl=price_pnl,
        modeled_costs=costs,
        net_pnl=net_pnl,
        net_return=_number(final / initial - 1),
        counterfactual_cost_drag_return=_number(
            gross_final / initial - final / initial
        ),
        periods=periods,
        max_reconciliation_error=max(errors, default=0.0),
        reconciled=True,
    )


def _cash_account(prices, account, initial, *, gross=False):
    if (
        not isinstance(account, dict)
        or account.get("accounting_model") != "self_financing_daily.v1"
        or account.get("quote_currency") not in CURRENCIES
    ):
        raise ValueError("UNSUPPORTED_CONTRIBUTION_ACCOUNT")
    periods = account.get("periods")
    if not isinstance(periods, list) or len(periods) != len(prices["dates"]) - 1:
        raise ValueError("INVALID_CONTRIBUTION_GRID")
    previous, errors, costs = initial, [], []
    contributions = {p: [] for p in prices["close"]}
    for index, row in enumerate(periods):
        if (
            not isinstance(row, dict)
            or row.get("date") != prices["dates"][index + 1]
            or not isinstance(row.get("positions"), dict)
            or set(row["positions"]) != set(contributions)
        ):
            raise ValueError("INVALID_CONTRIBUTION_GRID")
        equity = _number(row.get("equity"), minimum=0)
        if equity == 0:
            raise ValueError("INVALID_CONTRIBUTION_EQUITY")
        cash = _number(row.get("cash"), minimum=0)
        cost = _number(row.get("cost"), minimum=0)
        if gross and cost != 0:
            raise ValueError("GROSS_ACCOUNT_HAS_COSTS")
        held = {p: _number(v, minimum=0) for p, v in row["positions"].items()}
        errors.append(_match(_sum(held.values()) + cash, equity, previous, equity))
        changes = {}
        for product, value in held.items():
            series = prices["close"][product]
            quantity = _number(value / series[index + 1])
            changes[product] = _number(quantity * (series[index + 1] - series[index]))
            contributions[product].append(changes[product])
        errors.append(
            _match(_sum(changes.values()) - cost, equity - previous, previous, equity)
        )
        _match(row.get("net_return"), equity / previous - 1)
        costs.append(cost)
        previous = equity
    return (
        previous,
        {p: _sum(values) for p, values in contributions.items()},
        _sum(costs),
        errors,
    )


def explain_self_financing(
    prices: dict, net: dict, gross: dict, *, initial_equity: float = 1.0
) -> dict:
    initial = _number(initial_equity, minimum=0)
    if (
        initial == 0
        or not isinstance(prices, dict)
        or not isinstance(prices.get("close"), dict)
        or not prices["close"]
    ):
        raise ValueError("INVALID_CONTRIBUTION_INPUT")
    dates = _dates(prices.get("dates"))
    if len(dates) < 2:
        raise ValueError("INVALID_CONTRIBUTION_GRID")
    for product, series in prices["close"].items():
        if (
            not isinstance(product, str)
            or not product
            or not isinstance(series, list)
            or len(series) != len(dates)
        ):
            raise ValueError("INVALID_CONTRIBUTION_PRICES")
        if any(_number(v, minimum=0) == 0 for v in series):
            raise ValueError("INVALID_CONTRIBUTION_PRICES")
    final, contributions, costs, errors = _cash_account(prices, net, initial)
    gross_final, _, _, gross_errors = _cash_account(prices, gross, initial, gross=True)
    if net["quote_currency"] != gross["quote_currency"]:
        raise ValueError("CONTRIBUTION_CURRENCY_MISMATCH")
    return _report(
        "self_financing_daily.v1",
        net["quote_currency"],
        initial,
        final,
        gross_final,
        contributions,
        costs,
        errors + gross_errors,
        len(net["periods"]),
    )


def explain_fractional(
    portfolio: list[dict],
    positions: list[dict],
    gross_portfolio: list[dict],
    *,
    initial_equity: float,
    quote_currency: str,
) -> dict:
    initial = _number(initial_equity, minimum=0)
    if (
        initial == 0
        or quote_currency not in CURRENCIES
        or not isinstance(portfolio, list)
        or not isinstance(gross_portfolio, list)
        or not isinstance(positions, list)
    ):
        raise ValueError("INVALID_CONTRIBUTION_INPUT")
    dates = _dates([r.get("date") for r in portfolio if isinstance(r, dict)])
    if (
        len(dates) != len(portfolio)
        or len(gross_portfolio) != len(portfolio)
        or any(not isinstance(r, dict) for r in gross_portfolio)
    ):
        raise ValueError("INVALID_CONTRIBUTION_GRID")
    if [r.get("date") for r in gross_portfolio] != dates:
        raise ValueError("INVALID_CONTRIBUTION_GRID")
    groups, seen = {day: [] for day in dates}, set()
    for row in positions:
        if (
            not isinstance(row, dict)
            or row.get("date") not in groups
            or not isinstance(row.get("code"), str)
            or not row["code"]
        ):
            raise ValueError("INVALID_CONTRIBUTION_POSITIONS")
        key = row["date"], row["code"]
        if key in seen:
            raise ValueError("DUPLICATE_CONTRIBUTION_POSITION")
        seen.add(key)
        groups[row["date"]].append(row)
    contributions, costs, errors = {}, [], []
    previous, gross_previous = initial, initial
    for row, gross_row in zip(portfolio, gross_portfolio, strict=True):
        holdings = groups[row["date"]]
        if not holdings:
            raise ValueError("MISSING_CONTRIBUTION_POSITIONS")
        price_returns, cost_rates, net_returns, weights = [], [], [], []
        for position in holdings:
            weight = _number(position.get("target_weight"), minimum=0)
            if weight > 1:
                raise ValueError("UNSUPPORTED_CONTRIBUTION_LEVERAGE")
            change = _number(position.get("asset_return"))
            if change < -1:
                raise ValueError("INVALID_CONTRIBUTION_RETURN")
            cost_rate = _number(position.get("cost"), minimum=0)
            net_return = _number(position.get("strategy_return"))
            _match(weight * change - cost_rate, net_return)
            price_returns.append(weight * change)
            cost_rates.append(cost_rate)
            net_returns.append(net_return)
            weights.append(weight)
            contributions.setdefault(position["code"], []).append(
                _number(previous * weight * change)
            )
        if _sum(weights) > 1 + TOLERANCE:
            raise ValueError("UNSUPPORTED_CONTRIBUTION_LEVERAGE")
        daily = _sum(net_returns)
        _match(row.get("daily_return"), daily)
        equity = _number(row.get("equity"), minimum=0)
        gross_equity = _number(gross_row.get("equity"), minimum=0)
        if not equity or not gross_equity:
            raise ValueError("INVALID_CONTRIBUTION_EQUITY")
        _match(gross_row.get("daily_return"), _sum(price_returns))
        errors.append(_match(equity, previous * (1 + daily), previous, equity))
        errors.append(
            _match(
                gross_equity,
                gross_previous * (1 + _sum(price_returns)),
                gross_previous,
                gross_equity,
            )
        )
        cost = _number(previous * _sum(cost_rates))
        errors.append(
            _match(
                previous * _sum(price_returns) - cost,
                equity - previous,
                previous,
                equity,
            )
        )
        costs.append(cost)
        previous, gross_previous = equity, gross_equity
    return _report(
        "equity_fractional_proxy.v1",
        quote_currency,
        initial,
        previous,
        gross_previous,
        {p: _sum(values) for p, values in contributions.items()},
        _sum(costs),
        errors,
        len(portfolio),
    )
