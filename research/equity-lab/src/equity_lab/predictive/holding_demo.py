"""Deterministic synthetic-only installed producer for contract verification."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def synthetic_input():
    dates = pd.date_range("2025-01-01", periods=230, freq="B")
    schedule = pd.DataFrame(
        {
            "open": dates.tz_localize("UTC") + pd.Timedelta(hours=14),
            "close": dates.tz_localize("UTC") + pd.Timedelta(hours=21),
        },
        index=dates,
    )
    rows = []
    for i, day in enumerate(dates):
        for j in range(55):
            opening = 100 + j + i * 0.02
            closing = opening * (1 + 0.01 * np.sin(i * 0.31 + j * 0.47))
            rows.append(
                dict(
                    TradeDate=day,
                    ResearchKey=f"SYNTHETIC{j:03}",
                    Ticker=f"SYNTHETIC{j:03}",
                    open_price=opening,
                    close_price=closing,
                    high_price=max(opening, closing) * 1.001,
                    low_price=min(opening, closing) * 0.999,
                    dollar_volume=20_000_000 + j * 1000,
                    median_spread=0.0001,
                    valid_quote_minutes=400,
                    active_trade_minutes=400,
                )
            )
    return pd.DataFrame(rows), schedule


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if not args.output.is_absolute() or any(
        (p / ".git").exists() or (p / "pyproject.toml").exists()
        for p in (output, *output.parents)
    ):
        raise ValueError("SYNTHETIC_OUTPUT_MUST_BE_EXTERNAL")
    from .holding import run_holding

    report = run_holding(*synthetic_input(), output)
    print(
        json.dumps(
            dict(
                synthetic=True,
                accounts=len(report["accounts"]),
                fit_attempts=report["fit_attempts"],
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
