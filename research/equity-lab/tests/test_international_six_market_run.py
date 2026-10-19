import json
from pathlib import Path

import pandas as pd
import pytest

from equity_lab.international.six_market_run import (
    build_paper_shadow_ledger,
    run_experiment,
)


@pytest.mark.parametrize("destination", ["existing", "source"])
def test_output_refuses_existing_or_source_before_reading_config(tmp_path, destination):
    output = tmp_path / destination
    output.mkdir()
    if destination == "source":
        (output / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
        output = output / "new"
    with pytest.raises(ValueError, match="OUTPUT"):
        run_experiment(tmp_path / "missing.yml", output)


def test_paper_shadow_ledger_records_qualified_and_failed_contracts() -> None:
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-01"]),
            "rebalance_markets": ["US,HK"],
            "US_reference_price": [100.0],
            "HK_reference_price": [20.0],
            "US_trade_notional": [1000.0],
            "HK_trade_notional": [500.0],
        }
    )
    config = {
        "asset_proxies": {"US": "SPY", "HK": "2800"},
        "target_weights": {"US": 0.5, "HK": 0.5},
        "paper_shadow": {"slippage_bps": 5.0, "fee_bps": 2.0},
    }
    manifest = {
        "records": [{"kind": "asset", "market": "US", "symbol": "SPY", "conid": 123}]
    }
    ledger = build_paper_shadow_ledger(returns, config, manifest)
    assert set(ledger["status"]) == {"simulated", "failed"}
    assert ledger.loc[ledger["market"] == "US", "conid"].iloc[0] == 123
    assert ledger.loc[ledger["market"] == "HK", "reason"].iloc[0]


def test_run_writes_hashed_outputs_and_remains_exploration(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    daily = data_root / "raw" / "ibkr" / "daily"
    fx_root = data_root / "raw" / "ibkr" / "fx"
    daily.mkdir(parents=True)
    fx_root.mkdir(parents=True)
    dates = pd.date_range("2023-01-31", periods=25, freq="ME")
    markets = {
        "US": "USD",
        "HK": "HKD",
        "UK": "GBP",
        "AU": "AUD",
        "CA": "CAD",
        "SG": "SGD",
    }
    for market in markets:
        pd.DataFrame({"date": dates, "close": range(100, 125), "volume": 1000}).to_csv(
            daily / f"{market}.csv", index=False
        )
    for currency in ["HKD", "GBP", "AUD", "CAD", "SGD"]:
        pd.DataFrame({"date": dates, "usd_per_local": 0.1}).to_csv(
            fx_root / f"{currency}.csv", index=False
        )
    config = tmp_path / "experiment.yml"
    config.write_text(
        "experiment_id: demo\n"
        "data_root: " + str(data_root).replace("\\", "/") + "\n"
        "target_weights: {US: 0.25, HK: 0.125, UK: 0.125, AU: 0.125, CA: 0.125, SG: 0.25}\n"
        "costs_bps: {US: 5, HK: 5, UK: 5, AU: 5, CA: 5, SG: 5}\n"
        "asset_files: {US: raw/ibkr/daily/US.csv, HK: raw/ibkr/daily/HK.csv, "
        "UK: raw/ibkr/daily/UK.csv, AU: raw/ibkr/daily/AU.csv, "
        "CA: raw/ibkr/daily/CA.csv, SG: raw/ibkr/daily/SG.csv}\n"
        "fx_files: {HKD: raw/ibkr/fx/HKD.csv, GBP: raw/ibkr/fx/GBP.csv, "
        "AUD: raw/ibkr/fx/AUD.csv, CAD: raw/ibkr/fx/CAD.csv, "
        "SGD: raw/ibkr/fx/SGD.csv}\n"
        "paper_shadow_complete: false\n",
        encoding="utf-8",
    )
    output = tmp_path / "run"
    summary = run_experiment(config, output)
    assert summary["evidence_status"] == "exploration"
    assert summary["total_return_status"] == "unavailable"
    assert summary["metrics"]
    total_summary = json.loads((output / "total_return_summary.json").read_text())
    assert total_summary["metrics"] == {}
    assert (output / "inputs.lock.json").is_file()
    assert len(json.loads((output / "inputs.lock.json").read_text())["inputs"]) == 12
    for name in [
        "summary.json",
        "window_metrics.csv",
        "market_attribution.csv",
        "fx_attribution.csv",
        "rebalance_ledger.csv",
        "total_return_summary.json",
        "competition_metrics.csv",
        "dividend_attribution.csv",
        "decision.md",
    ]:
        assert (output / name).is_file()
    fx_attribution = pd.read_csv(output / "fx_attribution.csv")
    assert list(fx_attribution.columns) == ["status"]
    assert fx_attribution.loc[0, "status"] == "unavailable"
    shadow = pd.read_csv(output / "paper_shadow_ledger.csv")
    assert shadow["estimated_fee"].ge(0).all()
