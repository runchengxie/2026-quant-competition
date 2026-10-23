"""Independent NumPy cash algebra over sampled raw closes; no leaf imports."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .datasets.daily_storage import safe_path
from .datasets.storage import write_json
from .evaluation.controls.contracts import read_json
from .evaluation.controls.publication import _pairs
from .evaluation.controls.verification import (
    verify_plan,
    validate_results_index,
    verify_control_result,
)


def post_fee_nav(nav, positions, rate):
    positions = np.asarray(positions, dtype=float)
    if (
        not math.isfinite(nav)
        or nav <= 0
        or not positions.size
        or not np.isfinite(positions).all()
        or (positions < 0).any()
        or not math.isfinite(rate)
        or not 0 <= rate < 1
    ):
        raise ValueError("INVALID_REFERENCE_CASH")
    weights = np.full(len(positions), 1 / len(positions))
    breaks = sorted({0.0, nav, *(float(v) for v in positions / weights if 0 < v < nav)})
    # Within each interval, absolute trade dollars are linear in post-fee NAV.
    for low, high in zip(breaks, breaks[1:], strict=False):
        signs = np.sign(weights * ((low + high) / 2) - positions)
        result = (nav + rate * np.dot(signs, positions)) / (
            1 + rate * np.dot(signs, weights)
        )
        if low - 1e-12 <= result <= high + 1e-12:
            return float(result)
    raise ValueError("NO_REFERENCE_FEE_SOLUTION")


def _trajectory(prices, fee_bps, *, daily):
    shares, cash, periods = np.zeros(prices.shape[1]), 1.0, []
    for index, (before_prices, after_prices) in enumerate(
        zip(prices[251:-1], prices[252:], strict=True)
    ):
        positions = shares * before_prices
        before = float(positions.sum() + cash)
        cost, turnover = 0.0, 0.0
        if index == 0 or daily:
            after_fee = post_fee_nav(before, positions, fee_bps / 10000)
            desired = np.full(len(shares), after_fee / len(shares))
            turnover = float(np.abs(desired - positions).sum() / before)
            cost = fee_bps / 10000 * turnover * before
            shares = desired / before_prices
            cash = float(after_fee - desired.sum())
        marked = shares * after_prices
        equity = float(marked.sum() + cash)
        periods.append(
            dict(
                equity=equity,
                cash=cash,
                positions=marked,
                weights=marked / equity,
                turnover=turnover,
                cost=cost,
                net_return=equity / before - 1,
                exposure=float(marked.sum() / equity),
            )
        )
    return periods


def _summary(net, gross, annual):
    returns = np.array([p["net_return"] for p in net])
    equity = np.array([p["equity"] for p in net])
    deviation = float(returns.std(ddof=1)) if len(net) > 1 else 0.0
    return dict(
        periods=len(net),
        net_return=float(equity[-1] - 1),
        gross_return=gross[-1]["equity"] - 1,
        cost_drag=gross[-1]["equity"] - equity[-1],
        volatility=deviation * math.sqrt(annual),
        sharpe=float(returns.mean()) / deviation * math.sqrt(annual)
        if deviation
        else None,
        max_drawdown=float(
            np.max(1 - equity / np.maximum.accumulate(np.r_[1.0, equity])[1:])
        ),
        turnover=sum(p["turnover"] for p in net),
        total_costs=sum(p["cost"] for p in net),
        mean_daily_turnover=float(np.mean([p["turnover"] for p in net])),
        mean_exposure=float(np.mean([p["exposure"] for p in net])),
        flat_days=sum(p["exposure"] <= 1e-12 and p["turnover"] <= 1e-12 for p in net),
    )


def check_reference(plan_path, results_path, output_root):
    plan = verify_plan(plan_path)
    result = validate_results_index(plan, read_json(results_path))
    if result["status"] != "completed":
        raise ValueError("REFERENCE_REQUIRES_COMPLETE_GRID")
    root = safe_path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    by_id = {r["job_id"]: r for r in result["jobs"]}
    samples, rows = [], []
    for job in plan["jobs"]:
        record = by_id[job["job_id"]]
        path = safe_path(results_path.parent / record["result_path"])
        actual = verify_control_result(job, path)
        rows.append(
            {
                k: job[k]
                for k in ("job_id", "market", "arm_id", "fee_bps", "quote_currency")
            }
            | dict(
                start=job["fold"]["start"],
                end=job["fold"]["end"],
                metrics=actual["metrics"],
            )
        )
        market_jobs = [j for j in plan["jobs"] if j["market"] == job["market"]]
        edges = {
            min(j["fold"]["start"] for j in market_jobs),
            max(j["fold"]["start"] for j in market_jobs),
        }
        if (
            job["arm_id"] != ("ew_daily" if job["market"] == "US" else "ew_legacy")
            or job["fold"]["start"] not in edges
        ):
            continue
        products = sorted(job["products"])
        columns = []
        for product in products:
            with (
                Path(job["manifest"]).parent / "normalized" / (product + ".csv")
            ).open(encoding="utf-8-sig", newline="") as stream:
                table = {r["date"]: float(r["close"]) for r in csv.DictReader(stream)}
            columns.append([table[d] for d in job["dates"]])
        prices = np.array(columns).T
        net = _trajectory(prices, job["fee_bps"], daily=job["market"] == "US")
        gross = _trajectory(prices, 0, daily=job["market"] == "US")
        expected = _summary(net, gross, 252 if job["market"] == "US" else 365)
        errors = []
        for key, reference in expected.items():
            measured = actual["metrics"][key]
            if reference is None:
                if measured is not None:
                    raise ValueError("REFERENCE_SUMMARY_MISMATCH")
            else:
                errors.append(abs(measured - reference))
                if not math.isclose(measured, reference, rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError("REFERENCE_SUMMARY_MISMATCH")
        periods = read_json(path.parent / "periods.json")
        for side, reference in (("net", net), ("gross", gross)):
            for measured, computed in zip(periods[side], reference, strict=True):
                for key in (
                    "equity",
                    "cash",
                    "turnover",
                    "cost",
                    "net_return",
                    "exposure",
                ):
                    errors.append(abs(measured[key] - computed[key]))
                    if not math.isclose(
                        measured[key], computed[key], rel_tol=1e-9, abs_tol=1e-9
                    ):
                        raise ValueError("REFERENCE_PERIOD_MISMATCH")
                for key in ("positions", "weights"):
                    if not np.allclose(
                        [measured[key][p] for p in products],
                        computed[key],
                        atol=1e-9,
                        rtol=1e-9,
                    ):
                        raise ValueError("REFERENCE_HOLDINGS_MISMATCH")
        samples.append(
            dict(
                job_id=job["job_id"],
                market=job["market"],
                fee_bps=job["fee_bps"],
                largest_absolute_difference=float(max(errors)),
            )
        )
    pairs = _pairs(rows)
    lookup = {r["job_id"]: r for r in rows}
    for pair in pairs:
        left, right = lookup[pair["candidate_job_id"]], lookup[pair["control_job_id"]]
        if any(
            left[k] != right[k] or pair[k] != left[k]
            for k in ("market", "fee_bps", "start", "end")
        ):
            raise ValueError("REFERENCE_PAIR_CONTEXT_MISMATCH")
        identity = {
            k: pair[k]
            for k in (
                "market",
                "fee_bps",
                "start",
                "end",
                "candidate_job_id",
                "control_job_id",
            )
        }
        if (
            hashlib.sha256(
                json.dumps(
                    identity, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            != pair["pair_id"]
        ):
            raise ValueError("REFERENCE_PAIR_ID_MISMATCH")
        for field, metric in (
            ("net_return_change", "net_return"),
            ("drawdown_change", "max_drawdown"),
            ("turnover_change", "mean_daily_turnover"),
            ("exposure_change", "mean_exposure"),
        ):
            if not math.isclose(
                pair[field],
                float(np.subtract(left["metrics"][metric], right["metrics"][metric])),
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise ValueError("REFERENCE_PAIR_DELTA_MISMATCH")
    report = dict(
        schema="competition.strategy_controls_reference.v1",
        code_commit=plan["code_commit"],
        plan_sha256=plan["plan_sha256"],
        sampled_jobs=samples,
        independently_checked_pairs=len(pairs),
        reference="numpy_piecewise_fee_solution_from_raw_closes",
        limitation="sampled_equal_weight_accounting_not_full_policy_reimplementation",
    )
    write_json(root / "reference.json", report)
    write_json(root / "private-comparisons.json", dict(rows=rows, pairs=pairs))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "results", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    value = check_reference(args.plan, args.results, args.output_root)
    print(
        json.dumps(
            dict(
                sampled_jobs=len(value["sampled_jobs"]),
                checked_pairs=value["independently_checked_pairs"],
            )
        )
    )


if __name__ == "__main__":
    main()
