from pathlib import Path

import pandas as pd
import pytest

from equity_lab.international.six_market_inputs import (
    load_daily_asset,
    load_distributions,
    load_fx_series,
    validate_common_history,
    validate_distribution_coverage,
)


def test_loaders_normalize_valid_inputs(tmp_path: Path) -> None:
    asset = tmp_path / "asset.csv"
    asset.write_text(
        "date,close,volume\n2024-01-02,10,100\n2024-01-03,11,120\n", encoding="utf-8"
    )
    fx = tmp_path / "fx.csv"
    fx.write_text(
        "date,usd_per_local\n2024-01-02,0.1\n2024-01-03,0.1\n", encoding="utf-8"
    )
    loaded_asset = load_daily_asset(asset, "US")
    loaded_fx = load_fx_series(fx, "HKD")
    assert list(loaded_asset.columns) == [
        "date",
        "close",
        "volume",
        "market",
        "currency",
    ]
    assert loaded_asset["currency"].iloc[0] == "USD"
    assert loaded_fx["currency"].iloc[0] == "HKD"


def test_loaders_reject_duplicates_and_invalid_values(tmp_path: Path) -> None:
    asset = tmp_path / "asset.csv"
    asset.write_text(
        "date,close,volume\n2024-01-02,10,100\n2024-01-02,11,120\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        load_daily_asset(asset, "US")
    fx = tmp_path / "fx.csv"
    fx.write_text("date,usd_per_local\n2024-01-02,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-positive"):
        load_fx_series(fx, "HKD")


def test_common_history_requires_all_markets_and_24_months() -> None:
    dates = pd.date_range("2024-01-31", periods=24, freq="ME")
    asset = pd.DataFrame({"date": dates})
    assets = dict.fromkeys(["US", "HK", "UK", "AU", "CA", "SG"], asset)
    fx = dict.fromkeys(["HKD", "GBP", "AUD", "CAD", "SGD"], asset)
    result = validate_common_history(assets, fx)
    assert result["common_months"] == 24
    with pytest.raises(ValueError, match="minimum is 24"):
        validate_common_history(
            {key: value.iloc[:12] for key, value in assets.items()},
            {key: value.iloc[:12] for key, value in fx.items()},
        )


def test_distribution_loader_validates_cash_and_currency(tmp_path: Path) -> None:
    path = tmp_path / "dividends.csv"
    path.write_text(
        "date,cash_per_share,currency,source\n2024-01-03,0.25,USD,provider\n",
        encoding="utf-8",
    )
    loaded = load_distributions(path, "US", "USD")
    assert loaded.loc[0, "cash_per_share"] == 0.25
    assert loaded.loc[0, "market"] == "US"
    path.write_text(
        "date,cash_per_share,currency,source\n2024-01-03,-0.1,USD,provider\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="negative cash"):
        load_distributions(path, "US", "USD")
    path.write_text(
        "date,cash_per_share,currency,source\n2024-01-03,0.1,HKD,provider\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="currency mismatch"):
        load_distributions(path, "US", "USD")
    path.write_text(
        "date,cash_per_share,currency,source\n2024-01-03,inf,USD,provider\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite cash and source"):
        load_distributions(path, "US", "USD")


def test_distribution_coverage_reports_unavailable_and_complete() -> None:
    dates = pd.date_range("2024-01-31", periods=2, freq="ME")
    assets = {"US": pd.DataFrame({"date": dates})}
    distributions = {
        "US": pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-02-01"]),
                "cash_per_share": [0.1],
                "currency": ["USD"],
                "source": ["provider"],
                "market": ["US"],
            }
        )
    }
    result = validate_distribution_coverage(distributions, assets)
    assert result["US"]["status"] == "partial"
    assert result["HK"]["status"] == "unavailable"
