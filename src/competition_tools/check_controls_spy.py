"""Private SPY supplement from frozen controls inputs, without new policy runs."""

import argparse
import csv
import json
import math
from pathlib import Path

from .datasets.daily_storage import safe_path
from .datasets.storage import digest, write_json
from .evaluation.controls.contracts import read_json
from .evaluation.controls.verification import (
    verify_plan,
    validate_results_index,
    verify_control_result,
)


def spy_comparison(job, prices, strategy_net):
    """Enter before the first scored return and pay the same one-way entry fee."""
    try:
        before = job["dates"][job["fold"]["warmup_periods"] - 1]
        first, last = prices[before], prices[job["fold"]["end"]]
        fee = job["fee_bps"] / 10000
        if (
            not all(math.isfinite(v) for v in (first, last, fee, strategy_net))
            or min(first, last) <= 0
            or not 0 <= fee < 1
        ):
            raise ValueError
        gross, net = last / first - 1, last / first / (1 + fee) - 1
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("INVALID_SPY_COMPARISON_INPUT") from None
    return dict(
        spy_gross_price_return=gross,
        spy_fee_matched_net_return=net,
        strategy_net_return=strategy_net,
        excess_vs_spy_gross=strategy_net - gross,
        excess_vs_spy_fee_matched_net=strategy_net - net,
        entry_price_date=before,
    )


def check_spy(plan_path: Path, results_path: Path, output_root: Path):
    plan = verify_plan(plan_path)
    index = validate_results_index(plan, read_json(results_path))
    if index["status"] != "completed":
        raise ValueError("SPY_REQUIRES_COMPLETED_GRID")
    records = {r["job_id"]: r for r in index["jobs"]}
    rows, cache = [], {}
    for job in plan["jobs"]:
        if job["market"] != "US":
            continue
        path = safe_path(Path(job["manifest"]).parent / "normalized/SPY.csv")
        expected = next(
            r["sha256"] for r in job["input_files"] if r["path"] == "normalized/SPY.csv"
        )
        if digest(path) != expected:
            raise ValueError("SPY_INPUT_CHANGED")
        if expected not in cache:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                cache[expected] = {
                    r["date"]: float(r["close"]) for r in csv.DictReader(stream)
                }
        actual = verify_control_result(
            job, safe_path(results_path.parent / records[job["job_id"]]["result_path"])
        )
        rows.append(
            dict(
                job_id=job["job_id"],
                arm_id=job["arm_id"],
                fee_bps=job["fee_bps"],
                start=job["fold"]["start"],
                end=job["fold"]["end"],
                benchmark_sha256=expected,
                **spy_comparison(job, cache[expected], actual["metrics"]["net_return"]),
            )
        )
        if digest(path) != expected:
            raise ValueError("SPY_INPUT_CHANGED")
    report = dict(
        schema="competition.private_controls_spy_comparisons.v1",
        plan_sha256=plan["plan_sha256"],
        code_commit=plan["code_commit"],
        benchmark="SPY",
        price_basis="split_adjusted",
        return_basis="price_only_no_dividends",
        entry_fee="same_one_way_bps_post_fee_nav",
        terminal_liquidation=False,
        accepted_research=False,
        new_policy_runs=0,
        rows=rows,
    )
    output = safe_path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "us-spy-comparisons.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "results", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = check_spy(args.plan, args.results, args.output_root)
    print(json.dumps(dict(us_comparisons=len(report["rows"]), new_policy_runs=0)))


if __name__ == "__main__":
    main()
