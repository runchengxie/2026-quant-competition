"""Allowlisted public facts reconstructed from verified private study artifacts."""

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest, write_json
from .study_inputs import load_study_input
from .study_plan import plan_hash, validate_job, PARAMETERS, STRATEGIES, COSTS
from .study_runner import _result

POOLS = {
    "US": {
        "AAPL",
        "MSFT",
        "AMZN",
        "GOOGL",
        "META",
        "NVDA",
        "JPM",
        "JNJ",
        "XOM",
        "PG",
        "SPY",
    },
    "HK": {
        "0005",
        "0388",
        "0700",
        "0939",
        "0941",
        "1299",
        "1810",
        "2318",
        "3690",
        "9988",
        "2800",
    },
    "crypto": {
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "LINKUSDT",
    },
}
REASONS = {
    "INSUFFICIENT_HISTORY",
    "MARKET_INPUT_UNAVAILABLE",
    "INVALID_STUDY_INPUT",
    "INPUT_CHANGED",
    "CODE_CHANGED",
    "TIME_BUDGET",
    "INTERRUPTED",
    "STUDY_CHILD_FAILED",
    "INVALID_STUDY_RESULT",
    "INVALID_STUDY_ARTIFACT",
    "STUDY_INPUT_OR_CHILD_UNAVAILABLE",
    "INPUT_CHANGED_POST_RUN",
}
METRICS = "net_return gross_return sharpe volatility max_drawdown turnover mean_exposure cost_drag benchmark_return excess_return sessions mean_daily_position_proxy mean_daily_oneway_turnover_proxy flat_days_proxy".split()
TOP_KEYS = set(
    "schema as_of code_commit plan_sha256 methods coverage results blockers".split()
)
COVERAGE_KEYS = set(
    "market source status products benchmark quote_currency start end rows universe_status".split()
)
RESULT_KEYS = set(
    "job_id market status reason_code strategy method_id accounting_model fold start end products benchmark cost_bps quote_currency periods_per_year plan_sha256 result_sha256 eligibility_basis".split()
) | set(METRICS)
METHOD_KEYS = set(
    "method_id strategy signal_parameters signal_lag_periods rebalance execution_assumption warmup_periods scoring_periods fold_initialization cost_model terminal_liquidation retrospective".split()
)
BLOCKERS = [
    "RETROSPECTIVE_FIXED_CURRENT_POOL",
    "DAILY_EXECUTION_AND_ELIGIBILITY_PROXY",
    "EQUITY_DIVIDENDS_AND_ADJUSTMENT_TIMING_UNVERIFIED",
    "ACCOUNT_PRODUCT_AUTHORIZATION_SEPARATE",
    "MAKER_ARCHIVE_NOT_RERUN",
]


def validate_public_study(value):
    """Stdlib-only publication boundary; no unreviewed free-form strings."""

    def exact(obj, keys):
        if not isinstance(obj, dict) or set(obj) != keys:
            raise ValueError("INVALID_PUBLIC_STUDY_FIELDS")

    def match(pattern, text):
        if not isinstance(text, str) or not re.fullmatch(pattern, text):
            raise ValueError("INVALID_PUBLIC_STUDY_IDENTIFIER")

    def day(text):
        match(r"\d{4}-\d{2}-\d{2}", text)
        if datetime.fromisoformat(text).date().isoformat() != text:
            raise ValueError("INVALID_PUBLIC_STUDY_DATE")

    exact(value, TOP_KEYS)
    if (
        value["schema"] != "competition.public_study.v1"
        or value["blockers"] != BLOCKERS
    ):
        raise ValueError("INVALID_PUBLIC_STUDY_SCHEMA")
    day(value["as_of"])
    match(r"[a-f0-9]{40}", value["code_commit"])
    match(r"[a-f0-9]{64}", value["plan_sha256"])
    if (
        not all(isinstance(value[k], list) for k in ("methods", "coverage", "results"))
        or len(value["results"]) > 384
    ):
        raise ValueError("INVALID_PUBLIC_STUDY_LIST")
    methods = {}
    for method in value["methods"]:
        exact(method, METHOD_KEYS)
        parts = method["method_id"].split(".")
        market = {"us": "US", "hk": "HK", "crypto": "crypto"}.get(parts[0])
        strategy = method["strategy"]
        if (
            market not in POOLS
            or strategy not in STRATEGIES[market]
            or method["method_id"]
            != market.lower() + "." + strategy + ".self_financing_daily.v1"
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_METHOD")
        hold = strategy in {"buy_hold", "benchmark_buy_hold"} or (
            market == "crypto" and strategy == "equal_weight"
        )
        expected = dict(
            method_id=method["method_id"],
            strategy=strategy,
            signal_parameters=PARAMETERS[strategy],
            signal_lag_periods=1,
            rebalance="buy_hold" if hold else "daily_target_weights",
            execution_assumption="lagged_close_proxy",
            warmup_periods=252,
            scoring_periods=90 if market == "crypto" else 63,
            fold_initialization="independent_cash",
            cost_model="self_financing_oneway_bps",
            terminal_liquidation=False,
            retrospective=True,
        )
        if method != expected or method["method_id"] in methods:
            raise ValueError("INVALID_PUBLIC_STUDY_METHOD")
        methods[method["method_id"]] = method
    for coverage in value["coverage"]:
        exact(coverage, COVERAGE_KEYS)
        market = coverage["market"]
        if (
            market not in POOLS
            or coverage["source"]
            != ("binance_spot" if market == "crypto" else "ibkr_daily")
            or coverage["status"] not in {"acquired", "partial"}
            or coverage["universe_status"] != "fixed_current"
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_COVERAGE")
        if (
            not coverage["products"]
            or not set(coverage["products"]) <= POOLS[market]
            or coverage["benchmark"]
            != {"US": "SPY", "HK": "2800", "crypto": "equal_weight"}[market]
            or coverage["quote_currency"]
            != {"US": "USD", "HK": "HKD", "crypto": "USDT"}[market]
            or type(coverage["rows"]) is not int
            or coverage["rows"] <= 0
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_COVERAGE")
        day(coverage["start"])
        day(coverage["end"])
    ids = set()
    for row in value["results"]:
        exact(row, RESULT_KEYS)
        match(r"[a-f0-9]{64}", row["job_id"])
        if (
            row["job_id"] in ids
            or row["plan_sha256"] != value["plan_sha256"]
            or row["market"] not in {*POOLS, "unknown"}
            or row["status"] not in {"completed", "blocked", "failed"}
            or row["eligibility_basis"] != "daily_model_proxy"
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_RESULT")
        ids.add(row["job_id"])
        market = row["market"]
        if row["products"] and (
            market not in POOLS or not set(row["products"]) <= POOLS[market]
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_PRODUCTS")
        if row["strategy"] is not None:
            if (
                market not in POOLS
                or row["strategy"] not in STRATEGIES[market]
                or row["cost_bps"] not in COSTS[market]
                or row["quote_currency"]
                != {"US": "USD", "HK": "HKD", "crypto": "USDT"}[market]
                or row["benchmark"]
                != {"US": "SPY", "HK": "2800", "crypto": "equal_weight"}[market]
                or row["accounting_model"] != "self_financing_daily.v1"
                or row["periods_per_year"] != (365 if market == "crypto" else 252)
            ):
                raise ValueError("INVALID_PUBLIC_STUDY_IDENTITY")
            exact(
                row["fold"],
                set("warmup_start start end warmup_periods scoring_periods".split()),
            )
            for k in ("warmup_start", "start", "end"):
                day(row["fold"][k])
            if (
                row["start"] != row["fold"]["start"]
                or row["end"] != row["fold"]["end"]
                or row["fold"]["warmup_periods"] != 252
                or row["fold"]["scoring_periods"] != (90 if market == "crypto" else 63)
            ):
                raise ValueError("INVALID_PUBLIC_STUDY_FOLD")
        elif row["products"] or any(
            row[k] is not None
            for k in (
                "accounting_model",
                "fold",
                "start",
                "end",
                "benchmark",
                "cost_bps",
                "quote_currency",
                "periods_per_year",
            )
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_IDENTITY")
        if row["status"] != "completed":
            if (
                row["reason_code"] not in REASONS
                or any(row[k] is not None for k in METRICS)
                or row["result_sha256"] is not None
                or row["method_id"] is not None
            ):
                raise ValueError("INVALID_PUBLIC_STUDY_BLOCKER")
            continue
        match(r"[a-f0-9]{64}", row["result_sha256"])
        if (
            row["reason_code"] is not None
            or row["method_id"] not in methods
            or row["method_id"]
            != market.lower() + "." + row["strategy"] + ".self_financing_daily.v1"
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_COMPLETION")
        for key in METRICS:
            number = row[key]
            if number is None and key in {
                "sharpe",
                "benchmark_return",
                "excess_return",
            }:
                continue
            if type(number) not in (int, float) or not math.isfinite(number):
                raise ValueError("INVALID_PUBLIC_STUDY_METRIC")
        if (
            row["sessions"] != row["fold"]["scoring_periods"]
            or not 0 <= row["mean_exposure"] <= 1 + 1e-12
            or not 0 <= row["max_drawdown"] <= 1
            or not 0 <= row["flat_days_proxy"] <= row["sessions"]
        ):
            raise ValueError("INVALID_PUBLIC_STUDY_METRIC")
    return value


def project_study(aggregate: dict) -> dict:
    if (
        aggregate.get("schema") != "competition.study_results.v1"
        or aggregate.get("accepted_research") is not False
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    plan_path = safe_path(Path(aggregate["plan_path"]))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        plan.get("schema") != "competition.study_plan.v1"
        or plan_hash(plan) != aggregate["plan_sha256"]
        or plan["plan_sha256"] != aggregate["plan_sha256"]
        or plan["code_identity"]["commit"] != aggregate["code_commit"]
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    observed = datetime.fromisoformat(aggregate["observed_at"])
    if observed.tzinfo is None:
        raise ValueError("INVALID_STUDY_TIMESTAMP")
    planned = {j["job_id"]: j for j in plan["jobs"]}
    if (
        len(planned) != len(plan["jobs"])
        or len(planned) > 384
        or {r["job_id"] for r in aggregate["jobs"]} != set(planned)
        or len(aggregate["jobs"]) != len(planned)
    ):
        raise ValueError("INVALID_STUDY_AGGREGATE")
    coverage = []
    for data in plan["inputs"]:
        current = load_study_input(Path(data["manifest"]))
        if current != data or not set(data["products"]) <= POOLS[data["market"]]:
            raise ValueError("UNREVIEWED_STUDY_INPUT")
        coverage.append(
            dict(
                market=data["market"],
                source="binance_spot" if data["market"] == "crypto" else "ibkr_daily",
                status=data["parent_status"],
                products=data["products"],
                benchmark=data["benchmark"],
                quote_currency=data["quote_currency"],
                start=data["dates"][0],
                end=data["dates"][-1],
                rows=len(data["dates"])
                * (len(data["products"]) + (data["market"] != "crypto")),
                universe_status="fixed_current",
            )
        )
    results = []
    methods = {}
    verified = {}
    for record in aggregate["jobs"]:
        job = planned[record["job_id"]]
        validate_job(job)
        if (
            json.loads(
                (plan_path.parent / "jobs" / (job["job_id"] + ".json")).read_text(
                    encoding="utf-8"
                )
            )
            != job
            or job.get("plan_sha256") != plan["plan_sha256"]
        ):
            raise ValueError("FROZEN_JOB_CHANGED")
        market = job["market"]
        if market not in POOLS and market != "unknown":
            raise ValueError("UNREVIEWED_STUDY_MARKET")
        if record["market"] != market or record["status"] not in {
            "completed",
            "blocked",
            "failed",
        }:
            raise ValueError("INVALID_STUDY_AGGREGATE")
        planned_job = job["status"] == "planned"
        if planned_job and (
            not set(job["products"]) <= POOLS[market]
            or job["benchmark"]
            != {"US": "SPY", "HK": "2800", "crypto": "equal_weight"}[market]
        ):
            raise ValueError("UNREVIEWED_STUDY_PRODUCTS")
        row = dict(
            job_id=job["job_id"],
            market=market,
            status=record["status"],
            reason_code=record["reason"],
            strategy=job.get("strategy"),
            method_id=None,
            accounting_model=job.get("accounting_model"),
            fold=job.get("fold"),
            start=job.get("fold", {}).get("start"),
            end=job.get("fold", {}).get("end"),
            products=job.get("products", []),
            benchmark=job.get("benchmark"),
            cost_bps=job.get("fee_bps"),
            quote_currency=job.get("quote_currency"),
            periods_per_year=(365 if market == "crypto" else 252)
            if planned_job
            else None,
            plan_sha256=plan["plan_sha256"],
            result_sha256=None,
            eligibility_basis="daily_model_proxy",
        )
        row.update({k: None for k in METRICS})
        if record["status"] == "completed":
            if not planned_job or record["reason"] is not None:
                raise ValueError("FORGED_STUDY_COMPLETION")
            path = safe_path(Path(record["result_path"]))
            expected = safe_path(
                plan_path.parent / "run" / job["job_id"] / "result.json"
            )
            if path != expected or digest(path) != record["result_sha256"]:
                raise ValueError("STUDY_RESULT_CHANGED")
            result, _ = _result(job, path.parent)
            if result["metrics"] != record["metrics"]:
                raise ValueError("STUDY_METRICS_CHANGED")
            m = result["metrics"]
            method = result["methods"]
            methods[method["method_id"]] = method
            row.update(
                {
                    k: m[k]
                    for k in (
                        "net_return",
                        "gross_return",
                        "sharpe",
                        "volatility",
                        "max_drawdown",
                        "turnover",
                        "mean_exposure",
                        "cost_drag",
                    )
                }
            )
            row.update(
                method_id=method["method_id"],
                sessions=m["periods"],
                result_sha256=digest(path),
                mean_daily_position_proxy=m["mean_exposure"],
                mean_daily_oneway_turnover_proxy=m["mean_daily_turnover"],
                flat_days_proxy=m["flat_days"],
            )
            verified[job["job_id"]] = result
        elif record["reason"] not in REASONS or record["metrics"] is not None:
            raise ValueError("INVALID_STUDY_BLOCKER")
        results.append(row)
    benchmarks = {
        (r["market"], r["start"], r["end"], r["cost_bps"], r["quote_currency"]): r
        for r in results
        if r["status"] == "completed"
        and r["strategy"]
        == ("equal_weight" if r["market"] == "crypto" else "benchmark_buy_hold")
    }
    for row in results:
        if row["status"] == "completed":
            benchmark = benchmarks.get(
                (
                    row["market"],
                    row["start"],
                    row["end"],
                    row["cost_bps"],
                    row["quote_currency"],
                )
            )
            if benchmark is not None:
                row.update(
                    benchmark_return=benchmark["net_return"],
                    excess_return=row["net_return"] - benchmark["net_return"],
                )
    return validate_public_study(
        dict(
            schema="competition.public_study.v1",
            as_of=observed.date().isoformat(),
            code_commit=aggregate["code_commit"],
            plan_sha256=plan["plan_sha256"],
            methods=sorted(methods.values(), key=lambda m: m["method_id"]),
            coverage=coverage,
            results=results,
            blockers=BLOCKERS,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = project_study(
        json.loads(safe_path(args.aggregate).read_text(encoding="utf-8"))
    )
    if args.output.exists():
        raise ValueError("PUBLIC_STUDY_OUTPUT_EXISTS")
    write_json(safe_path(args.output), value)


if __name__ == "__main__":
    main()
