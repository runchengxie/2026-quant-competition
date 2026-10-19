"""Fixed-weight, USD-denominated monthly portfolio calculations."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

MARKETS = ("US", "HK", "UK", "AU", "CA", "SG")
LOCAL_CURRENCY = {
    "US": "USD",
    "HK": "HKD",
    "UK": "GBP",
    "AU": "AUD",
    "CA": "CAD",
    "SG": "SGD",
}


def build_month_end_calendar(assets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for market, frame in assets.items():
        dates = pd.DatetimeIndex(frame["date"]).sort_values()
        for _, month_frame in frame.assign(
            month=frame["date"].dt.to_period("M")
        ).groupby("month"):
            observation = month_frame["date"].max()
            following = dates[dates > observation]
            rows.append(
                {
                    "market": market,
                    "month": str(observation.to_period("M")),
                    "observation_date": observation,
                    "next_session": following[0] if len(following) else pd.NaT,
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "market"])
        .reset_index(drop=True)
    )


def _return_series(
    frame: pd.DataFrame, dates: pd.DatetimeIndex, market: str
) -> pd.Series:
    prices = frame.set_index("date")["close"].sort_index()
    aligned = prices.reindex(dates).ffill()
    if aligned.isna().any():
        raise ValueError(f"asset series has no prior close for {market}")
    source_gaps = prices.index.to_series().diff().dt.days.dropna()
    if (
        len(prices) >= 10
        and not source_gaps.empty
        and source_gaps.median() <= 7
        and source_gaps.max() > 7
    ):
        raise ValueError(f"asset series has stale/missing observations for {market}")
    return aligned.pct_change().fillna(0.0)


def _fx_series(frame: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    rates = frame.set_index("date")["usd_per_local"].sort_index()
    return rates.reindex(dates).ffill()


def compute_usd_returns(
    assets: dict[str, pd.DataFrame],
    fx: dict[str, pd.DataFrame],
    target_weights: Mapping[str, float],
    cost_bps: Mapping[str, float],
) -> pd.DataFrame:
    return compute_usd_return_components(assets, fx, {}, target_weights, cost_bps)


def compute_usd_return_components(
    assets: dict[str, pd.DataFrame],
    fx: dict[str, pd.DataFrame],
    distributions: dict[str, pd.DataFrame],
    target_weights: Mapping[str, float],
    cost_bps: Mapping[str, float],
) -> pd.DataFrame:
    if set(assets) != set(MARKETS):
        raise ValueError(
            "INCOMPLETE_UNIVERSE: assets must contain exactly the six configured markets"
        )
    if abs(sum(target_weights.values()) - 1.0) > 1e-9:
        raise ValueError("target weights must sum to 1")
    all_inputs = [*assets.values(), *fx.values()]
    common_start = max(frame["date"].min() for frame in all_inputs)
    dates = pd.DatetimeIndex(
        sorted(
            date
            for date in set().union(*(set(frame["date"]) for frame in assets.values()))
            if date >= common_start
        )
    )
    returns = pd.DataFrame(index=dates)
    price_returns: dict[str, pd.Series] = {}
    price_levels: dict[str, pd.Series] = {}
    dividend_returns: dict[str, pd.Series] = {}
    fx_returns: dict[str, pd.Series] = {}
    for market in MARKETS:
        local = _return_series(assets[market], dates, market)
        prices = assets[market].set_index("date")["close"].sort_index()
        price_levels[market] = prices.reindex(dates).ffill()
        cash = distributions.get(market, pd.DataFrame())
        dividend = pd.Series(0.0, index=dates)
        if not cash.empty:
            for distribution in cash.itertuples(index=False):
                effective_dates = prices.index[prices.index >= distribution.date]
                if not len(effective_dates):
                    raise ValueError(
                        f"distribution date is after asset history for {market}"
                    )
                effective_date = effective_dates[0]
                prior_prices = prices.loc[prices.index < effective_date]
                if prior_prices.empty:
                    raise ValueError(f"distribution has no prior close for {market}")
                dividend.loc[effective_date] += (
                    distribution.cash_per_share / prior_prices.iloc[-1]
                )
        currency = LOCAL_CURRENCY[market]
        if currency == "USD":
            fx_daily = pd.Series(0.0, index=dates)
        else:
            rates = _fx_series(fx[currency], dates)
            if rates.isna().any():
                raise ValueError(f"FX series has no prior rate for {currency}")
            fx_daily = rates.pct_change().fillna(0.0)
        price_returns[market] = (1.0 + local) * (1.0 + fx_daily) - 1.0
        dividend_returns[market] = dividend * (1.0 + fx_daily)
        fx_returns[market] = fx_daily
        returns[market] = (1.0 + price_returns[market]) * (1.0 + dividend) - 1.0

    calendar = build_month_end_calendar(assets)
    calendar["execution_date"] = calendar["next_session"].fillna(
        calendar["observation_date"]
    )
    rebalance_by_date = {
        date: group.to_dict("records")
        for date, group in calendar.groupby("execution_date")
    }
    holdings = pd.Series({market: float(target_weights[market]) for market in MARKETS})
    rows: list[dict[str, object]] = []
    for date, daily in returns.iterrows():
        total_before = float(holdings.sum())
        weights = (
            holdings / total_before
            if total_before
            else pd.Series(target_weights, dtype=float)
        )
        gross = float((weights * daily).sum())
        price_gross = float(
            sum(weights[market] * price_returns[market].loc[date] for market in MARKETS)
        )
        dividend_gross = float(
            sum(
                weights[market] * dividend_returns[market].loc[date]
                for market in MARKETS
            )
        )
        fx_gross = float(
            sum(weights[market] * fx_returns[market].loc[date] for market in MARKETS)
        )
        holdings = holdings * (1.0 + daily)
        turnover = 0.0
        cost_drag = 0.0
        trade_notionals = dict.fromkeys(MARKETS, 0.0)
        observation_dates: dict[str, str] = {}
        pre_trade_weights: dict[str, float] = {}
        rebalance_events = rebalance_by_date.get(date, [])
        for event in rebalance_events:
            market = str(event["market"])
            observation_dates[market] = str(
                pd.Timestamp(event["observation_date"]).date()
            )
            pre_trade_weights[market] = float(weights[market])
            target_value = total_before * float(target_weights[market])
            trade_value = target_value - float(holdings[market])
            trade_notionals[market] = abs(trade_value)
            turnover += abs(trade_value) / total_before if total_before else 0.0
            cost_drag += (
                abs(trade_value) / total_before * float(cost_bps[market]) / 10_000
                if total_before
                else 0.0
            )
            holdings[market] = target_value
        if cost_drag:
            holdings *= 1.0 - cost_drag
        row: dict[str, object] = {
            "date": date,
            "gross_return": gross,
            "price_return": price_gross,
            "dividend_return": dividend_gross,
            "fx_return": fx_gross,
            "total_return": gross,
            "cost_drag": cost_drag,
            "portfolio_return": gross - cost_drag,
            "turnover": turnover,
            "rebalance_markets": ",".join(
                event["market"] for event in rebalance_events
            ),
            "rebalance_observation_dates": ";".join(
                f"{market}={value}" for market, value in observation_dates.items()
            ),
            "rebalance_pre_trade_weights": ";".join(
                f"{market}={value}" for market, value in pre_trade_weights.items()
            ),
        }
        row.update({f"{market}_usd_return": float(daily[market]) for market in MARKETS})
        row.update(
            {
                f"{market}_dividend_return": float(dividend_returns[market].loc[date])
                for market in MARKETS
            }
        )
        row.update(
            {f"{market}_trade_notional": trade_notionals[market] for market in MARKETS}
        )
        row.update(
            {
                f"{market}_reference_price": float(price_levels[market].loc[date])
                for market in MARKETS
            }
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    statuses = [
        "complete"
        if market in distributions and not distributions[market].empty
        else "unavailable"
        for market in MARKETS
    ]
    result.attrs["total_return_status"] = (
        "complete"
        if all(status == "complete" for status in statuses)
        else "unavailable"
    )
    return result


def summarize_portfolio(returns: pd.DataFrame) -> dict[str, float]:
    daily = pd.to_numeric(returns["portfolio_return"], errors="raise").fillna(0.0)
    nav = (1.0 + daily).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    annualized_return = (
        float(nav.iloc[-1] ** (252.0 / len(daily)) - 1.0) if len(daily) else 0.0
    )
    annualized_volatility = (
        float(daily.std(ddof=1) * np.sqrt(252.0)) if len(daily) > 1 else 0.0
    )
    sharpe = annualized_return / annualized_volatility if annualized_volatility else 0.0
    return {
        "annualized_return": annualized_return,
        "annualized_sharpe": float(sharpe),
        "maximum_drawdown": float(drawdown.min()),
        "annualized_volatility": annualized_volatility,
        "turnover": float(returns.get("turnover", pd.Series(dtype=float)).sum()),
        "worst_month": float(
            daily.groupby(returns["date"].dt.to_period("M"))
            .apply(lambda x: (1.0 + x).prod() - 1.0)
            .min()
        )
        if len(daily)
        else 0.0,
    }


def summarize_competition_metrics(
    returns: pd.DataFrame, target_weights: Mapping[str, float]
) -> dict[str, float]:
    daily = pd.to_numeric(returns["portfolio_return"], errors="raise").fillna(0.0)
    nav = (1.0 + daily).cumprod()
    running_high = nav.cummax()
    trough = int((nav / running_high - 1.0).idxmin()) if len(nav) else 0
    recovery_days = 0
    if len(nav) and trough < len(nav) - 1:
        prior_high = running_high.iloc[trough]
        recovered = nav.iloc[trough + 1 :] >= prior_high
        if recovered.any():
            recovery_days = int(recovered.index[recovered][0] - trough)
    monthly = daily.groupby(returns["date"].dt.to_period("M")).apply(
        lambda values: (1.0 + values).prod() - 1.0
    )
    price = pd.to_numeric(returns.get("price_return", daily), errors="raise").fillna(
        0.0
    )
    return {
        "recovery_days": float(recovery_days),
        "monthly_hit_rate": float((monthly > 0).mean()) if len(monthly) else 0.0,
        "effective_market_concentration": float(
            1.0 / sum(float(weight) ** 2 for weight in target_weights.values())
        ),
        "fx_exposure": float(
            returns.get("fx_return", pd.Series(0.0, index=returns.index)).abs().mean()
        ),
        "cost_drag": float(
            returns.get("cost_drag", pd.Series(0.0, index=returns.index)).sum()
        ),
        "dividend_contribution": float(
            returns.get("dividend_return", pd.Series(0.0, index=returns.index)).sum()
        ),
        "price_total_return_spread": float(
            (1.0 + daily).prod() / (1.0 + price).prod() - 1.0
        ),
    }


__all__ = [
    "build_month_end_calendar",
    "compute_usd_return_components",
    "compute_usd_returns",
    "summarize_competition_metrics",
    "summarize_portfolio",
]
