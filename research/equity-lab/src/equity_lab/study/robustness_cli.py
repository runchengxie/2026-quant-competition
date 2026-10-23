"""Independent fixed-grid robustness CLI, with no execution-package imports."""

import argparse
import json
from pathlib import Path

from .controls_inputs import read_json, validate_controls_job
from .inputs import _external, _source_hash, _digest, _hash, _load_prices, _write
from .robustness import evaluate_robustness, POOLS, STOCKS
from .controls import build_control_targets
from .accounting import account_periods, summarize

CATALOG_SHA256 = "aadddf9e8db01904471576c9efaf1bb0fa563cd2f1fe870c9fbfc72b0c3a8a0c"
KEYS = set(
    "schema input_job parent_result parent_result_sha256 pool_id fee_bps market products expected_leaf_sha256 catalog_sha256 code_commit accepted_research job_id plan_sha256".split()
)


def validate_job(job):
    if (
        set(job) != KEYS
        or job["schema"] != "competition.strategy_robustness_job.v1"
        or job["market"] != "US"
        or job["catalog_sha256"] != CATALOG_SHA256
        or job["accepted_research"] is not False
    ):
        raise ValueError("INVALID_ROBUSTNESS_JOB")
    base = validate_controls_job(job["input_job"])
    if (
        job["job_id"]
        != _hash({k: v for k, v in job.items() if k not in {"job_id", "plan_sha256"}})
        or type(job["fee_bps"]) is not int
        or base["market"] != "US"
    ):
        raise ValueError("INVALID_ROBUSTNESS_IDENTITY")
    if (
        base["arm_id"] != "ew_monthly"
        or set(base["products"]) != STOCKS
        or job["pool_id"] not in POOLS
        or job["pool_id"] == "full_pool"
        or job["products"] != sorted(POOLS[job["pool_id"]])
        or job["fee_bps"] != base["fee_bps"]
    ):
        raise ValueError("INVALID_US_ROBUSTNESS_POLICY")
    if (
        _source_hash() != job["expected_leaf_sha256"]
        or _digest(_external(job["parent_result"])) != job["parent_result_sha256"]
    ):
        raise ValueError("ROBUSTNESS_SOURCE_OR_PARENT_CHANGED")
    return job


def run_job(job, destination):
    validate_job(job)
    base = job["input_job"]
    request = base | {"strategy": "equal_weight"}
    bars = _load_prices(request)
    computation = evaluate_robustness(bars, job["pool_id"], fee_bps=job["fee_bps"])
    selected = dict(
        dates=bars["dates"], close={p: bars["close"][p] for p in job["products"]}
    )
    targets = build_control_targets(selected, "ew_monthly")["targets"]
    benchmark_request = base | {"strategy": "benchmark_buy_hold", "products": ["SPY"]}
    benchmark_bars = _load_prices(benchmark_request)
    benchmark_prices = dict(
        dates=benchmark_bars["dates"][251:],
        close={"SPY": benchmark_bars["close"]["SPY"][251:]},
    )
    benchmark_targets = [{"SPY": 1.0} for _ in benchmark_prices["dates"][1:]]
    net = account_periods(
        benchmark_prices,
        benchmark_targets,
        fee_bps=job["fee_bps"],
        quote_currency="USD",
    )
    gross = account_periods(
        benchmark_prices, benchmark_targets, fee_bps=0, quote_currency="USD"
    )
    benchmark = summarize(net, gross, periods_per_year=252)
    benchmark_periods = dict(
        net=net["periods"],
        gross=gross["periods"],
        prices=benchmark_prices,
        targets=benchmark_targets,
    )
    if _load_prices(benchmark_request) != benchmark_bars:
        raise ValueError("BENCHMARK_CHANGED")
    prices = dict(
        dates=bars["dates"][251:],
        close={p: bars["close"][p][251:] for p in job["products"]},
    )
    if _load_prices(request) != bars or _source_hash() != job["expected_leaf_sha256"]:
        raise ValueError("ROBUSTNESS_INPUT_OR_SOURCE_CHANGED")
    destination.mkdir(parents=True, exist_ok=False)
    periods = dict(
        schema="competition.strategy_robustness_periods.v1",
        job_id=job["job_id"],
        plan_sha256=job["plan_sha256"],
        net=computation["net"]["periods"],
        gross=computation["gross"]["periods"],
        prices=prices,
        targets=targets,
        benchmark_periods=benchmark_periods,
    )
    _write(destination / "periods.json", periods)
    result = {
        k: job[k]
        for k in (
            "job_id",
            "plan_sha256",
            "market",
            "pool_id",
            "fee_bps",
            "expected_leaf_sha256",
            "accepted_research",
        )
    }
    result.update(
        schema="competition.strategy_robustness_result.v1",
        status="completed",
        metrics=computation["metrics"],
        benchmark=benchmark,
        diagnostics=computation["diagnostics"],
        artifact=dict(
            path="periods.json",
            sha256=_digest(destination / "periods.json"),
            bytes=(destination / "periods.json").stat().st_size,
        ),
    )
    _write(destination / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        batch = read_json(args.batch)
        if (
            set(batch) != {"schema", "market", "plan_sha256", "jobs"}
            or batch["schema"] != "competition.strategy_robustness_batch.v1"
            or batch["market"] != "US"
            or not isinstance(batch["jobs"], list)
            or not 1 <= len(batch["jobs"]) <= 66
        ):
            raise ValueError("INVALID_ROBUSTNESS_BATCH")
        jobs = [validate_job(j) for j in batch["jobs"]]
        if len({j["job_id"] for j in jobs}) != len(jobs) or any(
            j["plan_sha256"] != batch["plan_sha256"] for j in jobs
        ):
            raise ValueError("INVALID_ROBUSTNESS_BATCH_IDENTITY")
        out = _external(args.output_root)
        out.mkdir(parents=True, exist_ok=False)
        rows = []
        for job in jobs:
            try:
                run_job(job, out / job["job_id"])
                status = "completed"
            except (ValueError, OSError, KeyError, TypeError, IndexError):
                status = "blocked"
            rows.append(dict(job_id=job["job_id"], status=status))
        result = dict(
            schema="competition.strategy_robustness_batch_result.v1",
            plan_sha256=batch["plan_sha256"],
            jobs=rows,
            status="completed"
            if all(r["status"] == "completed" for r in rows)
            else "partial",
        )
        _write(out / "batch-result.json", result)
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        print(
            json.dumps(
                dict(
                    status="blocked", issue_codes=["INVALID_ROBUSTNESS_BATCH_OR_INPUT"]
                )
            )
        )
        return 2
    print(json.dumps(dict(status=result["status"], jobs=len(rows))))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
