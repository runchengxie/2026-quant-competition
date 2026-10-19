"""Export daily target decisions from the unchanged legacy engine.

Dates remain session labels. A separate explicit clock artifact is required for replay.
"""

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
import math
import re

import pandas as pd

from equity_lab.backtest.engine import run_equal_weight_backtest


def _decimal(value):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError("NONFINITE_LEGACY_VALUE")
    return format(value.normalize(), "f")


def _session_date(value):
    timestamp = pd.Timestamp(value)
    if not isinstance(timestamp, pd.Timestamp):
        raise ValueError("INVALID_SESSION_DATE")
    return timestamp.strftime("%Y-%m-%d")


def export_decisions(
    signal_df, config, *, strategy_id, market, synthetic, input_fingerprint
):
    if (
        strategy_id not in {"equal_weight", "momentum_20d"}
        or market not in {"HK", "US"}
        or type(synthetic) is not bool
    ):
        raise ValueError("UNSUPPORTED_LEGACY_PROFILE")
    if (
        not isinstance(input_fingerprint, str)
        or re.fullmatch("[0-9a-f]{64}", input_fingerprint) is None
    ):
        raise ValueError("INVALID_INPUT_FINGERPRINT")
    required = {"date", "code", "close", "signal"}
    if not required <= set(signal_df.columns) or signal_df.empty:
        raise ValueError("INVALID_LEGACY_FRAME")
    source = signal_df.copy()
    dates = pd.to_datetime(source["date"], errors="raise")
    if dates.dt.tz is not None or (dates != dates.dt.normalize()).any():
        raise ValueError("AMBIGUOUS_SESSION_LABEL")
    source["date"] = dates
    if (
        source.duplicated(["date", "code"]).any()
        or len(source) != source["date"].nunique() * source["code"].nunique()
    ):
        raise ValueError("UNALIGNED_SESSION_GRID")
    if not all(
        isinstance(code, str) and code.startswith(market + ".")
        for code in source["code"]
    ):
        raise ValueError("INSTRUMENT_MARKET_MISMATCH")
    for key in ("close", "signal", "precomputed_weight", "weight_score", "dividend"):
        if key not in source:
            continue
        if any(isinstance(value, bool) for value in source[key]):
            raise ValueError("INVALID_LEGACY_NUMBER")
        values = pd.to_numeric(source[key], errors="raise")
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("NONFINITE_LEGACY_VALUE")
        if key == "close" and (values <= 0).any():
            raise ValueError("INVALID_PRICE")
        if key == "dividend" and (values != 0).any():
            raise ValueError("UNSUPPORTED_DIVIDEND_BASIS")
    portfolio, detail = run_equal_weight_backtest(source, config)
    decisions = []
    session_dates = sorted(detail["date"].unique())
    for previous, current in zip(session_dates, session_dates[1:]):
        group = detail[detail["date"] == current]
        decisions.append(
            {
                "source_date": _session_date(previous),
                "execution_date": _session_date(current),
                "weights": {
                    str(row.code): _decimal(row.target_weight)
                    for row in group.itertuples()
                },
            }
        )
    configuration = asdict(config)
    fingerprint = hashlib.sha256(
        json.dumps(
            configuration,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return {
        "schema_version": "competition.legacy_decisions.v1",
        "producer": "equity-lab",
        "strategy_id": strategy_id,
        "market": market,
        "frequency": "daily",
        "synthetic": synthetic,
        "input_fingerprint": input_fingerprint,
        "legacy_config": configuration,
        "legacy_config_fingerprint": fingerprint,
        "decisions": decisions,
        "legacy": {
            "initial_cash": str(float(config.initial_capital)),
            "final_nav": str(float(portfolio.iloc[-1]["equity"])),
            "observations": len(portfolio),
            "commission_bps": _decimal(
                Decimal(str(config.commission_bps))
                + Decimal(str(config.regulation_bps))
                + Decimal(str(config.sec_fee_bps))
            ),
            "slippage_bps": _decimal(config.slippage_bps),
            "turnover_basis": "sum_absolute_target_weight_changes",
            "return_basis": "lagged_fractional_weight_price_proxy",
            "cash_model": "residual_weight_without_fx",
        },
    }


def synthetic_demo(output_root, market, strategy_id):
    from datetime import date, timedelta
    from pathlib import Path
    from equity_lab.backtest.engine import BacktestConfig
    from equity_lab.strategies.registry import load_strategy_module

    root = Path(output_root).resolve()
    if any((parent / ".git").exists() for parent in (root, *root.parents)):
        raise ValueError("OUTPUT_IN_SOURCE")
    root.mkdir(parents=True, exist_ok=False)
    bars = [
        {
            "date": (date(2026, 1, 16) + timedelta(days=i)).isoformat(),
            "code": market + ".DEMO_" + suffix,
            "close": str(100.0 + i * scale),
        }
        for i in range(32)
        for suffix, scale in [("A", 1.0), ("B", 0.25)]
    ]
    source = {
        "schema_version": "competition.synthetic_daily_bars.v1",
        "synthetic": True,
        "market": market,
        "bars": bars,
    }
    raw = json.dumps(
        source, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    (root / "bars.json").write_bytes(raw)
    frame = pd.DataFrame(bars)
    frame["close"] = frame["close"].astype(float)
    module = load_strategy_module(strategy_id)
    signals = module.build_signal_frame(frame)
    result = export_decisions(
        signals,
        BacktestConfig(initial_capital=10000.0, commission_bps=1.0, slippage_bps=2.0),
        strategy_id=strategy_id,
        market=market,
        synthetic=True,
        input_fingerprint=hashlib.sha256(raw).hexdigest(),
    )
    (root / "legacy.json").write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    return {
        "status": "synthetic_exported",
        "strategy_id": strategy_id,
        "market": market,
    }


def main():
    import argparse
    from pathlib import Path

    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError("INVALID_ARGUMENTS")

    try:
        parser = Parser(
            description="Export existing daily decisions using explicitly synthetic bars."
        )
        parser.add_argument("--synthetic-demo", action="store_true", required=True)
        parser.add_argument("--market", choices=["HK", "US"], required=True)
        parser.add_argument(
            "--strategy", choices=["equal_weight", "momentum_20d"], required=True
        )
        parser.add_argument("--output-root", type=Path, required=True)
        args = parser.parse_args()
        print(json.dumps(synthetic_demo(args.output_root, args.market, args.strategy)))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print(
            json.dumps({"status": "blocked", "issue_codes": ["LEGACY_EXPORT_INVALID"]})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
