import pandas as pd
import pytest

from equity_lab.international.six_market_portfolio import (
    build_month_end_calendar,
    compute_usd_return_components,
    compute_usd_returns,
    summarize_competition_metrics,
    summarize_portfolio,
)


def _inputs() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29"])
    assets = {
        market: pd.DataFrame(
            {"date": dates, "close": [100, 101, 102, 103], "volume": 1000}
        )
        for market in ["US", "HK", "UK", "AU", "CA", "SG"]
    }
    fx_dates = dates
    fx = {
        currency: pd.DataFrame(
            {"date": fx_dates, "usd_per_local": [1.0, 1.0, 1.1, 1.1]}
        )
        for currency in ["HKD", "GBP", "AUD", "CAD", "SGD"]
    }
    return assets, fx


def test_frozen_synthetic_financial_components_match_original_owner():
    assets, fx = _inputs()
    weights = dict(zip(assets, [0.25, 0.125, 0.125, 0.125, 0.125, 0.25], strict=True))
    result = compute_usd_returns(assets, fx, weights, dict.fromkeys(weights, 0.0))
    assert result["portfolio_return"].tolist() == pytest.approx(
        [0.0, 0.010000000000000009, 0.08564356435643572, 0.009803921568627416]
    )


def test_missing_canada_is_explicitly_blocked():
    assets, fx = _inputs()
    del assets["CA"]
    with pytest.raises(ValueError, match="INCOMPLETE_UNIVERSE"):
        compute_usd_returns(
            assets, fx, dict.fromkeys(assets, 0.2), dict.fromkeys(assets, 0.0)
        )


def test_calendar_uses_last_local_session_and_next_session() -> None:
    assets, _ = _inputs()
    calendar = build_month_end_calendar(assets)
    january = calendar[
        (calendar["market"] == "US") & (calendar["month"] == "2024-01")
    ].iloc[0]
    assert january["observation_date"] == pd.Timestamp("2024-01-31")
    assert january["next_session"] == pd.Timestamp("2024-02-01")


def test_portfolio_converts_fx_and_applies_fixed_weight_costs() -> None:
    assets, fx = _inputs()
    returns = compute_usd_returns(
        assets,
        fx,
        {"US": 0.25, "HK": 0.125, "UK": 0.125, "AU": 0.125, "CA": 0.125, "SG": 0.25},
        dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 10.0),
    )
    assert returns["portfolio_return"].notna().all()
    assert (returns["cost_drag"] >= 0).all()
    assert (
        returns.loc[
            returns["date"] == pd.Timestamp("2024-02-01"), "UK_usd_return"
        ].iloc[0]
        > 0.0
    )
    assert returns["turnover"].sum() >= 0.0


def test_summary_reports_drawdown_and_sharpe_keys() -> None:
    assets, fx = _inputs()
    returns = compute_usd_returns(
        assets,
        fx,
        dict(
            zip(
                ["US", "HK", "UK", "AU", "CA", "SG"],
                [0.25, 0.125, 0.125, 0.125, 0.125, 0.25],
                strict=True,
            )
        ),
        dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 0.0),
    )
    summary = summarize_portfolio(returns)
    assert {
        "annualized_return",
        "annualized_sharpe",
        "maximum_drawdown",
        "turnover",
    } <= summary.keys()


def test_portfolio_rejects_stale_asset_history_instead_of_zero_filling() -> None:
    assets, fx = _inputs()
    dates = pd.date_range("2024-01-02", periods=25, freq="B")
    for market in assets:
        assets[market] = pd.DataFrame(
            {"date": dates, "close": range(100, 125), "volume": 1000}
        )
    for currency in fx:
        fx[currency] = pd.DataFrame({"date": dates, "usd_per_local": 0.1})
    assets["HK"] = assets["HK"].drop(index=range(2, 10)).reset_index(drop=True)
    try:
        compute_usd_returns(
            assets,
            fx,
            {
                "US": 0.25,
                "HK": 0.125,
                "UK": 0.125,
                "AU": 0.125,
                "CA": 0.125,
                "SG": 0.25,
            },
            dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 10.0),
        )
    except ValueError as error:
        assert "stale/missing" in str(error)
    else:
        raise AssertionError("stale asset history must be rejected")


def test_return_components_include_dividend_and_fx_contributions() -> None:
    assets, fx = _inputs()
    distributions = {
        market: pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-02-01"]),
                "cash_per_share": [1.0],
                "currency": [
                    "USD"
                    if market == "US"
                    else {
                        "HK": "HKD",
                        "UK": "GBP",
                        "AU": "AUD",
                        "CA": "CAD",
                        "SG": "SGD",
                    }[market]
                ],
                "source": ["fixture"],
                "market": [market],
            }
        )
        for market in assets
    }
    result = compute_usd_return_components(
        assets,
        fx,
        distributions,
        {"US": 0.25, "HK": 0.125, "UK": 0.125, "AU": 0.125, "CA": 0.125, "SG": 0.25},
        dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 0.0),
    )
    row = result.loc[result["date"] == pd.Timestamp("2024-02-01")].iloc[0]
    assert row["dividend_return"] > 1.0 / 101.0
    assert row["fx_return"] != 0.0
    assert row["total_return"] > row["price_return"]
    assert result.attrs["total_return_status"] == "complete"


def test_missing_distributions_are_explicitly_unavailable() -> None:
    assets, fx = _inputs()
    result = compute_usd_return_components(
        assets,
        fx,
        {},
        {"US": 0.25, "HK": 0.125, "UK": 0.125, "AU": 0.125, "CA": 0.125, "SG": 0.25},
        dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 0.0),
    )
    assert result.attrs["total_return_status"] == "unavailable"


def test_non_session_distribution_is_applied_on_next_asset_session() -> None:
    assets, fx = _inputs()
    distributions = {
        market: pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-02-02"]),
                "cash_per_share": [1.0],
                "currency": [
                    "USD"
                    if market == "US"
                    else {
                        "HK": "HKD",
                        "UK": "GBP",
                        "AU": "AUD",
                        "CA": "CAD",
                        "SG": "SGD",
                    }[market]
                ],
                "source": ["fixture"],
                "market": [market],
            }
        )
        for market in assets
    }
    result = compute_usd_return_components(
        assets,
        fx,
        distributions,
        {"US": 0.25, "HK": 0.125, "UK": 0.125, "AU": 0.125, "CA": 0.125, "SG": 0.25},
        dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], 0.0),
    )
    row = result.loc[result["date"] == pd.Timestamp("2024-02-29")].iloc[0]
    assert row["US_dividend_return"] > 0.0


def test_competition_metrics_report_recovery_and_attribution() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.DataFrame(
        {
            "date": dates,
            "portfolio_return": [0.01, -0.10, 0.02, 0.10, 0.01],
            "price_return": [0.00, -0.10, 0.01, 0.08, 0.00],
            "dividend_return": [0.01, 0.00, 0.01, 0.01, 0.01],
            "fx_return": [0.00, 0.00, 0.01, 0.01, 0.00],
            "cost_drag": [0.0] * 5,
            "turnover": [0.0] * 5,
        }
    )
    metrics = summarize_competition_metrics(
        returns,
        {"US": 0.25, "HK": 0.125, "UK": 0.125, "AU": 0.125, "CA": 0.125, "SG": 0.25},
    )
    assert metrics["recovery_days"] == 2
    assert metrics["monthly_hit_rate"] == 1.0
    assert metrics["effective_market_concentration"] > 0.0
    assert metrics["dividend_contribution"] > 0.0
    assert metrics["price_total_return_spread"] > 0.0
