"""Exercise actual fixed-version accounting in separate environments on synthetic inputs."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess

from competition_tools.accounting_comparison import (
    PROVIDER,
    SafeParser,
    bind_clocks,
    digest,
    monthly_export,
    verify_and_compare,
)


def _write(path, value):
    path.write_text(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _run(python, module, *args):
    process = subprocess.run(
        [str(python), "-m", module, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    if process.returncode:
        raise ValueError("SYNTHETIC_CHILD_FAILED")
    return json.loads(process.stdout)


def build_inputs(root, legacy, bars_path):
    if legacy["synthetic"] is not True:
        raise ValueError("SYNTHETIC_ONLY")
    raw = Path(bars_path).read_bytes()
    bars = json.loads(raw)
    if (
        bars.get("schema_version") != "competition.synthetic_daily_bars.v1"
        or bars.get("synthetic") is not True
        or bars.get("market") != legacy["market"]
    ):
        raise ValueError("SYNTHETIC_ONLY")
    if hashlib.sha256(raw).hexdigest() != legacy["input_fingerprint"]:
        raise ValueError("SOURCE_CHANGED")
    root = Path(root).resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("OUTPUT_IN_SOURCE")
    root.mkdir(parents=True, exist_ok=False)
    by_date = {}
    for row in bars["bars"]:
        by_date.setdefault(row["date"], {})[row["code"]] = row["close"]
    dates = sorted(by_date)
    final = dates[-1] + "T16:00:00Z"
    clock_map = {
        "schema_version": "competition.decision_clocks.v1",
        "input_fingerprint": legacy["input_fingerprint"],
        "legacy_config_fingerprint": legacy["legacy_config_fingerprint"],
        "decisions": {},
    }
    for decision in legacy["decisions"]:
        previous, current = decision["source_date"], decision["execution_date"]
        clock = {
            "schema_version": "research.clock.v1",
            "timezone": "UTC",
            "information_cutoff_at": previous + "T16:00:00Z",
            "signal_at": previous + "T16:00:00Z",
            "decision_at": previous + "T16:01:00Z",
            "valuation_at": final,
            "timing_policy_id": "synthetic-previous-close-next-mark.v1",
            "trading_calendar_ref": "synthetic-daily.v1",
            "earliest_order_at": current + "T09:00:00Z",
            "execution_window_start_at": current + "T09:00:00Z",
            "execution_window_end_at": current + "T09:00:00Z",
        }
        clock_map["decisions"][current] = {
            "source_date": previous,
            "clock": clock,
            "execution_times": {
                code: current + "T09:00:00Z" for code in decision["weights"]
            },
        }
    decisions = bind_clocks(legacy, clock_map)
    codes = sorted({code for row in legacy["decisions"] for code in row["weights"]})
    hk = legacy["market"] == "HK"
    instruments = [
        {
            "instrument_id": code,
            "asset_type": "equity",
            "currency": "HKD" if hk else "USD",
            "lot_size": 100 * (i + 1) if hk else 1,
            "session_policy_id": "synthetic-session.v1",
        }
        for i, code in enumerate(codes)
    ]
    prices = []

    def price(code, at, value):
        return {
            "instrument_id": code,
            "price_at": at,
            "available_at": at,
            "price": value,
            "unit": "currency_per_share",
            "availability_basis": "verified",
            "session_policy_id": "synthetic-session.v1",
            "execution_eligible": True,
        }

    for index, day in enumerate(dates):
        for code in codes:
            prices.append(price(code, day + "T16:00:00Z", by_date[day][code]))
            if index:
                prices.append(
                    price(code, day + "T09:00:00Z", by_date[dates[index - 1]][code])
                )
    fx = (
        [
            {
                "base_currency": "HKD",
                "quote_currency": "USD",
                "price_at": day + "T00:00:00Z",
                "available_at": day + "T00:00:00Z",
                "rate": "0.125",
                "unit": "quote_per_base",
                "availability_basis": "verified",
            }
            for day in dates
        ]
        if hk
        else []
    )
    root_clock = (
        deepcopy(decisions[0]["clock"])
        if decisions
        else {
            "schema_version": "research.clock.v1",
            "timezone": "UTC",
            "information_cutoff_at": dates[0] + "T00:00:00Z",
            "signal_at": dates[0] + "T00:00:00Z",
            "decision_at": dates[0] + "T00:00:00Z",
            "valuation_at": final,
            "timing_policy_id": "synthetic-cash.v1",
            "trading_calendar_ref": "synthetic-daily.v1",
            "earliest_order_at": None,
            "execution_window_start_at": None,
            "execution_window_end_at": None,
        }
    )
    if decisions:
        root_clock["execution_window_end_at"] = decisions[-1]["clock"][
            "execution_window_end_at"
        ]
    asset = {
        "schema_version": "competition.accounting_inputs.v1",
        "market": legacy["market"],
        "synthetic": True,
        "upstream_input_fingerprint": legacy["input_fingerprint"],
        "instruments": instruments,
        "prices": prices,
        "fx": fx,
        "decisions": decisions,
        "valuation_times": [day + "T16:00:00Z" for day in dates],
        "research_clock": root_clock,
    }
    _write(root / "asset.json", asset)
    config = {
        "initial_cash": legacy["legacy"]["initial_cash"],
        "sizing_mode": "integral" if hk else "fractional",
        "commission_bps": legacy["legacy"]["commission_bps"],
        "slippage_bps": legacy["legacy"]["slippage_bps"],
        "fx_cost_bps": "0",
        "max_price_age_seconds": 172800,
        "max_fx_age_seconds": 172800,
        "fx_pairs": {"HKD": ["HKD", "USD"]} if hk else {},
        "allow_assumed_availability": False,
        "return_basis": "price",
        "allow_modeled_execution_prices": False,
    }
    input_sha = hashlib.sha256((root / "asset.json").read_bytes()).hexdigest()
    request = {
        "schema_version": "competition.accounting_request.v2",
        "provider": PROVIDER,
        "run_id": legacy["market"] + "-" + legacy["strategy_id"],
        "market": legacy["market"],
        "synthetic": True,
        "evidence": "software_diagnostic",
        "input_ref": {
            "artifact_id": "synthetic:accounting-inputs.v1",
            "relative_path": "asset.json",
            "sha256": input_sha,
            "size_bytes": (root / "asset.json").stat().st_size,
        },
        "input_fingerprint": input_sha,
        "config": config,
        "config_fingerprint": digest(config),
    }
    _write(root / "request.json", request)
    _write(root / "clocks.json", clock_map)
    _write(root / "legacy.json", legacy)
    return root


def run_checks(output_root, *, leaf_python, provider_python):
    from strategies.hk_low_frequency.backtest import DailyBar, HKBacktestConfig

    root = Path(output_root).resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("OUTPUT_IN_SOURCE")
    root.mkdir(parents=True, exist_ok=False)
    results = []
    for market in ("HK", "US"):
        for strategy in (
            "equal_weight",
            "momentum_20d",
            "pure_momentum",
            "momentum_volatility",
        ):
            source_dir = root / (market + "-" + strategy + "-producer")
            if strategy in {"equal_weight", "momentum_20d"}:
                _run(
                    leaf_python,
                    "equity_lab.accounting_export",
                    "--synthetic-demo",
                    "--market",
                    market,
                    "--strategy",
                    strategy,
                    "--output-root",
                    source_dir,
                )
                legacy = json.loads(
                    (source_dir / "legacy.json").read_text(encoding="utf-8")
                )
                bars_path = source_dir / "bars.json"
            else:
                bars_path = root / (market + "-equal_weight-producer") / "bars.json"
                source = json.loads(bars_path.read_text(encoding="utf-8"))
                history = {}
                for row in source["bars"]:
                    history.setdefault(row["code"], []).append(
                        DailyBar(row["date"], float(row["close"]), 1000.0)
                    )
                legacy = monthly_export(
                    history,
                    next(iter(history.values())),
                    HKBacktestConfig(
                        commission_bps=1.0,
                        slippage_bps=2.0,
                        lookbacks=(2,),
                        momentum_weights=(1.0,),
                        volatility_window=2,
                        top_k=1,
                        max_weight=0.6,
                        mode=strategy,
                    ),
                    market=market,
                    synthetic=True,
                    input_fingerprint=hashlib.sha256(
                        bars_path.read_bytes()
                    ).hexdigest(),
                    initial_cash="10000",
                )
            case = build_inputs(root / (market + "-" + strategy), legacy, bars_path)
            _run(
                provider_python,
                "platform_compare.cli",
                "run",
                "--request",
                case / "request.json",
                "--dataset-root",
                case,
                "--output",
                case / "bundle",
            )
            result = verify_and_compare(
                case / "legacy.json",
                case / "clocks.json",
                provider_python=provider_python,
                request_path=case / "request.json",
                dataset_root=case,
                bundle=case / "bundle",
            )
            # Retain private full diagnostics; stdout is an aggregate with no file paths.
            _write(case / "comparison.json", result)
            results.append(
                {
                    "market": market,
                    "strategy_id": strategy,
                    "frequency": result["frequency"],
                    "legacy_nav": result["legacy"]["final_nav"],
                    "owner_nav_usd": result["owner"]["final_nav_usd"],
                    "cash_usd": result["owner"]["final_cash_usd"],
                    "costs_usd": result["owner"]["total_costs_usd"],
                    "nav_difference_usd": result["nav_difference_usd"],
                    "status": "synthetic_diagnostic",
                }
            )
    summary = {
        "schema_version": "competition.accounting_demo.v1",
        "synthetic": True,
        "cases": results,
        "accepted_research": False,
    }
    _write(root / "summary.json", summary)
    return summary


def main():
    try:
        parser = SafeParser(description=__doc__)
        for name in ("output-root", "leaf-python", "provider-python"):
            parser.add_argument("--" + name, type=Path, required=True)
        args = parser.parse_args()
        print(
            json.dumps(
                run_checks(
                    args.output_root,
                    leaf_python=args.leaf_python,
                    provider_python=args.provider_python,
                )
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "issue_codes": ["SYNTHETIC_ACCOUNTING_CHECK_FAILED"],
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
