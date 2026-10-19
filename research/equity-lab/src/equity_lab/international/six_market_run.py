"""Run and publish the six-market research-only portfolio experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .six_market_inputs import (
    load_daily_asset,
    load_distributions,
    load_fx_series,
    validate_common_history,
    validate_distribution_coverage,
)
from .six_market_portfolio import (
    compute_usd_return_components,
    compute_usd_returns,
    summarize_competition_metrics,
    summarize_portfolio,
)
from .paths import external_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def _window_metrics(returns: pd.DataFrame) -> pd.DataFrame:
    end = returns["date"].max()
    rows: list[dict[str, Any]] = []
    for label, months in [
        ("full", None),
        ("24m", 24),
        ("12m", 12),
        ("6m", 6),
        ("3m", 3),
    ]:
        start = (
            returns["date"].min()
            if months is None
            else end - pd.DateOffset(months=months)
        )
        window = returns.loc[returns["date"] >= start]
        if window.empty:
            continue
        rows.append({"window": label, **summarize_portfolio(window)})
    return pd.DataFrame(rows)


def _window_competition_metrics(
    returns: pd.DataFrame, target_weights: dict[str, float]
) -> pd.DataFrame:
    end = returns["date"].max()
    rows: list[dict[str, Any]] = []
    for label, months in [
        ("full", None),
        ("24m", 24),
        ("12m", 12),
        ("6m", 6),
        ("3m", 3),
    ]:
        start = (
            returns["date"].min()
            if months is None
            else end - pd.DateOffset(months=months)
        )
        window = returns.loc[returns["date"] >= start]
        if not window.empty:
            rows.append(
                {
                    "window": label,
                    **summarize_competition_metrics(window, target_weights),
                }
            )
    return pd.DataFrame(rows)


def build_paper_shadow_ledger(
    returns: pd.DataFrame, config: dict[str, Any], acquisition_manifest: dict[str, Any]
) -> pd.DataFrame:
    records = {
        record.get("market"): record
        for record in acquisition_manifest.get("records", [])
        if record.get("kind") == "asset"
    }
    shadow = config.get("paper_shadow", {})
    slippage_bps = float(shadow.get("slippage_bps", 0.0))
    fee_bps = float(shadow.get("fee_bps", 0.0))
    rows: list[dict[str, object]] = []
    for _, event in returns.loc[returns["rebalance_markets"] != ""].iterrows():
        for market in str(event["rebalance_markets"]).split(","):
            contract = records.get(market)
            symbol = str(config.get("asset_proxies", {}).get(market, ""))
            qualified = contract is not None and str(contract.get("symbol")) == symbol
            reference_price = float(
                event.get(f"{market}_reference_price", float("nan"))
            )
            trade_notional = float(event.get(f"{market}_trade_notional", 0.0))
            observation_map = {
                item.split("=", 1)[0]: item.split("=", 1)[1]
                for item in str(event.get("rebalance_observation_dates", "")).split(";")
                if "=" in item
            }
            weight_map = {
                item.split("=", 1)[0]: float(item.split("=", 1)[1])
                for item in str(event.get("rebalance_pre_trade_weights", "")).split(";")
                if "=" in item
            }
            estimated_fee = trade_notional * fee_bps / 10_000
            rows.append(
                {
                    "observation_date": observation_map.get(market),
                    "execution_date": event["date"],
                    "market": market,
                    "symbol": symbol,
                    "conid": contract.get("conid") if qualified else None,
                    "target_weight": config.get("target_weights", {}).get(market),
                    "pre_trade_weight": weight_map.get(market),
                    "trade_notional": trade_notional,
                    "reference_price": reference_price,
                    "simulated_fill_price": reference_price
                    * (1.0 + slippage_bps / 10_000),
                    "slippage_bps": slippage_bps,
                    "fee_bps": fee_bps,
                    "estimated_fee": estimated_fee,
                    "status": "simulated" if qualified else "failed",
                    "reason": "qualified contract"
                    if qualified
                    else "missing or mismatched IBKR contract",
                }
            )
    return pd.DataFrame(rows)


def run_experiment(config_path: Path, output_dir: Path) -> dict[str, object]:
    output_dir = external_path(output_dir)
    if output_dir.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data_root = external_path(Path(config["data_root"]))
    assets = {
        market: load_daily_asset(_resolve(data_root, path), market)
        for market, path in config["asset_files"].items()
    }
    fx = {
        currency: load_fx_series(_resolve(data_root, path), currency)
        for currency, path in config["fx_files"].items()
    }
    currencies = {
        "US": "USD",
        "HK": "HKD",
        "UK": "GBP",
        "AU": "AUD",
        "CA": "CAD",
        "SG": "SGD",
    }
    distributions = {}
    distribution_paths = config.get("distribution_files", {})
    for market in config["asset_files"]:
        path_value = distribution_paths.get(market)
        path = _resolve(data_root, path_value) if path_value else None
        distributions[market] = (
            load_distributions(path, market, currencies[market])
            if path and path.is_file()
            else pd.DataFrame()
        )
    distribution_coverage = validate_distribution_coverage(distributions, assets)
    history = validate_common_history(assets, fx, minimum_months=24)
    price_returns = compute_usd_returns(
        assets, fx, config["target_weights"], config["costs_bps"]
    )
    total_returns = compute_usd_return_components(
        assets, fx, distributions, config["target_weights"], config["costs_bps"]
    )
    total_returns.attrs["total_return_status"] = (
        "complete"
        if all(item["status"] == "complete" for item in distribution_coverage.values())
        else "unavailable"
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    input_paths = [config_path]
    input_paths.extend(
        _resolve(data_root, path) for path in config["asset_files"].values()
    )
    input_paths.extend(
        _resolve(data_root, path) for path in config["fx_files"].values()
    )
    input_paths.extend(
        _resolve(data_root, path)
        for path in distribution_paths.values()
        if _resolve(data_root, path).is_file()
    )
    manifest_path = (
        _resolve(data_root, config["source_manifest"])
        if config.get("source_manifest")
        else None
    )
    if manifest_path and manifest_path.is_file():
        input_paths.append(manifest_path)
    lock = {
        "schema_version": "global_six_market.inputs_lock.v1",
        "data_root": str(data_root),
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)} for path in input_paths
        ],
        "distribution_coverage": distribution_coverage,
    }
    acquisition_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path and manifest_path.is_file()
        else {"records": []}
    )
    if manifest_path and manifest_path.is_file():
        lock["ibkr_acquisition"] = acquisition_manifest
    (output_dir / "inputs.lock.json").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "schema_version": "global_six_market.summary.v1",
        "experiment_id": config["experiment_id"],
        "evidence_status": "exploration",
        "history": history,
        "metrics": summarize_portfolio(price_returns),
        "paper_shadow_complete": bool(config.get("paper_shadow_complete", False)),
        "total_return_status": total_returns.attrs["total_return_status"],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "window_metrics.csv", _window_metrics(price_returns))
    total_status = total_returns.attrs["total_return_status"]
    total_summary = {
        "schema_version": "global_six_market.total_return_summary.v1",
        "experiment_id": config["experiment_id"],
        "evidence_status": "exploration",
        "total_return_status": total_returns.attrs["total_return_status"],
        "metrics": summarize_portfolio(total_returns)
        if total_status == "complete"
        else {},
    }
    (output_dir / "total_return_summary.json").write_text(
        json.dumps(total_summary, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(
        output_dir / "competition_metrics.csv",
        _window_competition_metrics(total_returns, config["target_weights"])
        if total_status == "complete"
        else pd.DataFrame(
            [
                {"window": label, "status": "unavailable"}
                for label in ["full", "24m", "12m", "6m", "3m"]
            ]
        ),
    )
    ledger_columns = [
        "date",
        "rebalance_markets",
        "gross_return",
        "cost_drag",
        "portfolio_return",
        "turnover",
    ]
    _write_csv(
        output_dir / "rebalance_ledger.csv",
        total_returns.loc[total_returns["rebalance_markets"] != "", ledger_columns],
    )
    _write_csv(
        output_dir / "paper_shadow_ledger.csv",
        build_paper_shadow_ledger(total_returns, config, acquisition_manifest),
    )

    attribution_rows = []
    fx_rows = []
    for market, weight in config["target_weights"].items():
        usd_return = price_returns[f"{market}_usd_return"]
        attribution_rows.append(
            {
                "market": market,
                "target_weight": weight,
                "mean_daily_usd_return": float(usd_return.mean()),
                "annualized_usd_contribution": float(
                    usd_return.mean() * 252.0 * weight
                ),
            }
        )
        currency = {
            "US": "USD",
            "HK": "HKD",
            "UK": "GBP",
            "AU": "AUD",
            "CA": "CAD",
            "SG": "SGD",
        }[market]
        if currency != "USD" and total_status == "complete":
            local = (
                assets[market]
                .set_index("date")["close"]
                .pct_change()
                .reindex(pd.DatetimeIndex(total_returns["date"]))
                .fillna(0.0)
            )
            local.index = total_returns.index
            fx_rows.append(
                {
                    "currency": currency,
                    "mean_daily_fx_contribution": float((usd_return - local).mean()),
                }
            )
    _write_csv(output_dir / "market_attribution.csv", pd.DataFrame(attribution_rows))
    _write_csv(
        output_dir / "fx_attribution.csv",
        pd.DataFrame(fx_rows)
        if total_status == "complete"
        else pd.DataFrame([{"status": "unavailable"}]),
    )
    dividend_rows = [
        {
            "market": market,
            "target_weight": weight,
            "mean_daily_dividend_return": float(
                total_returns[f"{market}_dividend_return"].mean()
            ),
            "annualized_dividend_contribution": float(
                total_returns[f"{market}_dividend_return"].mean() * 252.0 * weight
            ),
        }
        for market, weight in config["target_weights"].items()
    ]
    _write_csv(
        output_dir / "dividend_attribution.csv",
        pd.DataFrame(dividend_rows)
        if total_status == "complete"
        else pd.DataFrame([{"status": "unavailable"}]),
    )
    decision = "exploration"
    (output_dir / "decision.md").write_text(
        "# Global six-market decision\n\n"
        f"Status: `{decision}`\n\n"
        "The run is research-only. Production eligibility remains blocked until all configured "
        "contracts, 24 common months, immutable input hashes, attribution, and paper/shadow "
        "evidence are reviewed.\n",
        encoding="utf-8",
    )
    return summary


__all__ = ["run_experiment"]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--json", action="store_true", help="Emit the machine-readable result (default)"
    )
    args = parser.parse_args(argv)
    try:
        summary = run_experiment(args.config, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "issue_codes": ["INVALID_EXPERIMENT"],
                    "orders_submitted": False,
                    "accepted_research": False,
                }
            )
        )
        return 2
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
