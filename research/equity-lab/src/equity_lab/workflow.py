"""Bounded fictional-data acceptance of preparation, signals, replay and metrics."""

import argparse
import hashlib
import json
import math
import platform
import re
from datetime import date
from importlib.metadata import distributions
from pathlib import Path

import pandas as pd

from .backtest.engine import BacktestConfig, run_equal_weight_backtest
from .data.preparation import prepare_market_panel
from .evaluation.performance import compute_backtest_metrics
from .run_guard import source_digest
from .signals.sma import generate_sma_signal
from .study.inputs import _external

FILES = (
    "prepared.csv",
    "signals.csv",
    "portfolio.csv",
    "positions.csv",
    "gross-portfolio.csv",
    "summary.json",
)


def _validate(job):
    try:
        if (
            set(job) != {"schema", "project", "synthetic", "parameters", "data"}
            or job["schema"] != "competition.workflow_job.v1"
            or job["project"] != "equity-lab"
            or job["synthetic"] is not True
        ):
            raise ValueError
        p, data = job["parameters"], job["data"]
        if set(p) != {
            "initial_equity",
            "fee_bps",
            "quote_currency",
            "short_window",
            "long_window",
        } or set(data) != {"rows", "dates"}:
            raise ValueError
        if (
            any(
                type(p[k]) not in (int, float) or not math.isfinite(p[k])
                for k in ("initial_equity", "fee_bps")
            )
            or not 0 < p["initial_equity"] <= 1e9
            or not 0 <= p["fee_bps"] <= 100
            or p["quote_currency"] not in {"USD", "HKD"}
        ):
            raise ValueError
        if (
            type(p["short_window"]) is not int
            or type(p["long_window"]) is not int
            or not 0 < p["short_window"] < p["long_window"] <= 100
        ):
            raise ValueError
        dates, rows = data["dates"], data["rows"]
        if (
            not isinstance(dates, list)
            or not p["long_window"] < len(dates) <= 200
            or dates != sorted(set(dates))
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
            or not isinstance(rows, list)
            or not 0 < len(rows) <= 1000
        ):
            raise ValueError
        seen = set()
        for row in rows:
            if (
                set(row) != {"date", "code", "open", "high", "low", "close", "volume"}
                or row["date"] not in dates
                or not isinstance(row["code"], str)
                or not re.fullmatch(r"(?:US|HK)\.DEMO_[A-Z0-9_]+", row["code"])
            ):
                raise ValueError
            if (
                any(
                    type(row[k]) not in (int, float)
                    or not math.isfinite(row[k])
                    or row[k] <= 0
                    for k in ("open", "high", "low", "close")
                )
                or type(row["volume"]) not in (int, float)
                or not math.isfinite(row["volume"])
                or row["volume"] < 0
            ):
                raise ValueError
            identity = row["date"], row["code"]
            if identity in seen:
                raise ValueError
            seen.add(identity)
        json.dumps(job, allow_nan=False)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("INVALID_SYNTHETIC_WORKFLOW_JOB") from error


def _write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _records(frame):
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")
    return result.to_dict(orient="records")


def run_workflow(
    job: dict, output_root: Path, *, input_sha256: str | None = None
) -> dict:
    _validate(job)
    code = source_digest()
    out = _external(Path(output_root))
    out.mkdir(parents=True, exist_ok=False)
    parameters = job["parameters"]
    prepared = prepare_market_panel(
        pd.DataFrame(job["data"]["rows"]), trading_dates=job["data"]["dates"]
    )
    signals = generate_sma_signal(
        prepared,
        short_window=parameters["short_window"],
        long_window=parameters["long_window"],
    )
    config = BacktestConfig(
        initial_capital=parameters["initial_equity"],
        commission_bps=parameters["fee_bps"],
        slippage_bps=0.0,
    )
    portfolio, positions = run_equal_weight_backtest(signals, config)
    gross, _ = run_equal_weight_backtest(
        signals,
        BacktestConfig(
            initial_capital=parameters["initial_equity"],
            commission_bps=0.0,
            slippage_bps=0.0,
        ),
    )
    metrics = compute_backtest_metrics(
        portfolio, initial_capital=parameters["initial_equity"], signal_df=signals
    )
    for name, frame in zip(
        FILES[:5], (prepared, signals, portfolio, positions, gross), strict=True
    ):
        with (out / name).open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(
                stream, index=False, date_format="%Y-%m-%d", float_format="%.17g"
            )
    _write(out / "summary.json", metrics)
    if source_digest() != code:
        raise ValueError("WORKFLOW_SOURCE_CHANGED")
    result = dict(
        schema="competition.workflow_leaf_result.v1",
        status="completed",
        project="equity-lab",
        synthetic=True,
        accounting_model="equity_fractional_proxy.v1",
        quote_currency=parameters["quote_currency"],
        initial_equity=parameters["initial_equity"],
        parameters=parameters,
        input_sha256=input_sha256
        or hashlib.sha256(
            json.dumps(
                job, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest(),
        code_sha256=code,
        environment=dict(
            python=platform.python_version(),
            distributions=dict(
                sorted(
                    (d.metadata["Name"], d.version)
                    for d in distributions()
                    if d.metadata["Name"]
                )
            ),
        ),
        metrics=metrics,
        evidence=dict(
            portfolio=_records(portfolio),
            positions=_records(
                positions[
                    [
                        "date",
                        "code",
                        "target_weight",
                        "asset_return",
                        "cost",
                        "strategy_return",
                    ]
                ]
            ),
            gross_portfolio=_records(gross),
        ),
        artifacts=[
            dict(
                path=name,
                sha256=hashlib.sha256((out / name).read_bytes()).hexdigest(),
                bytes=(out / name).stat().st_size,
            )
            for name in FILES
        ],
    )
    _write(out / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    path = _external(args.input)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("WORKFLOW_INPUT_TOO_LARGE")
    body = path.read_bytes()
    result = run_workflow(
        json.loads(body),
        args.output_root,
        input_sha256=hashlib.sha256(body).hexdigest(),
    )
    print(
        json.dumps(
            dict(status=result["status"], project=result["project"], synthetic=True)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
