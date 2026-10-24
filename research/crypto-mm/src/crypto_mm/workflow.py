"""Bounded fictional daily acceptance without maker, provider or broker activity."""

import argparse
import hashlib
import json
import math
import platform
import re
from importlib.metadata import distributions
from pathlib import Path

from .data.daily_prices import validate_prices
from .portfolio.daily import build_control_targets
from .portfolio.rebalance import weekly_flags
from .daily.study_accounting import account_periods, summarize
from .daily.study_inputs import _external
from .run_guard import source_digest

FILES = ("prices.json", "targets.json", "net.json", "gross.json", "summary.json")


def _validate(job):
    try:
        if (
            set(job) != {"schema", "project", "synthetic", "parameters", "data"}
            or job["schema"] != "competition.workflow_job.v1"
            or job["project"] != "crypto-mm"
            or job["synthetic"] is not True
        ):
            raise ValueError
        p, data = job["parameters"], job["data"]
        if (
            set(p)
            != {
                "initial_equity",
                "fee_bps",
                "quote_currency",
                "arm_id",
                "decision_schedule",
            }
            or type(p["initial_equity"]) not in (int, float)
            or p["initial_equity"] != 1
            or type(p["fee_bps"]) not in (int, float)
            or not math.isfinite(p["fee_bps"])
            or not 0 <= p["fee_bps"] <= 100
        ):
            raise ValueError
        if (
            p["quote_currency"] != "USDT"
            or p["arm_id"] != "trend200_vol40_strict"
            or p["decision_schedule"] != "weekly_monday"
            or set(data) != {"dates", "close"}
        ):
            raise ValueError
        validate_prices(data)
        if (
            not 253 <= len(data["dates"]) <= 365
            or not 1 <= len(data["close"]) <= 5
            or any(
                not re.fullmatch(r"DEMO_[A-Z0-9_]+_USDT", product)
                for product in data["close"]
            )
        ):
            raise ValueError
        json.dumps(job, allow_nan=False)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("INVALID_SYNTHETIC_WORKFLOW_JOB") from error


def _write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run_workflow(
    job: dict, output_root: Path, *, input_sha256: str | None = None
) -> dict:
    _validate(job)
    code = source_digest()
    out = _external(Path(output_root))
    out.mkdir(parents=True, exist_ok=False)
    parameters, bars = job["parameters"], job["data"]
    generated = build_control_targets(bars, parameters["arm_id"])
    prices = dict(
        dates=bars["dates"][251:],
        close={p: row[251:] for p, row in bars["close"].items()},
    )
    flags = weekly_flags(prices["dates"][:-1])
    net = account_periods(
        prices,
        generated["targets"],
        fee_bps=parameters["fee_bps"],
        quote_currency="USDT",
        decision_flags=flags,
    )
    gross = account_periods(
        prices,
        generated["targets"],
        fee_bps=0,
        quote_currency="USDT",
        decision_flags=flags,
    )
    metrics = summarize(net, gross, periods_per_year=365)
    values = (
        prices,
        dict(
            targets=generated["targets"],
            decision_flags=flags,
            diagnostics=generated["diagnostics"],
        ),
        net,
        gross,
        metrics,
    )
    for name, value in zip(FILES, values, strict=True):
        _write(out / name, value)
    if source_digest() != code:
        raise ValueError("WORKFLOW_SOURCE_CHANGED")
    result = dict(
        schema="competition.workflow_leaf_result.v1",
        status="completed",
        project="crypto-mm",
        synthetic=True,
        accounting_model="self_financing_daily.v1",
        quote_currency="USDT",
        initial_equity=1,
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
        evidence=dict(prices=prices, net=net, gross=gross),
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
