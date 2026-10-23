"""Validate independently produced result identities and ledger arithmetic."""

from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest
from ..ablation_runner import _verify_period_metrics
from ..controls.contracts import read_json
from .contracts import validate_job


def verify_robustness_result(job: dict, result_path: Path) -> dict:
    validate_job(job)
    path = safe_path(result_path)
    before = digest(path)
    value = read_json(path)
    if (
        value.get("schema") != "competition.strategy_robustness_result.v1"
        or value.get("status") != "completed"
        or value.get("accepted_research") is not False
    ):
        raise ValueError("INVALID_ROBUSTNESS_RESULT")
    for key in (
        "job_id",
        "plan_sha256",
        "market",
        "pool_id",
        "fee_bps",
        "expected_leaf_sha256",
    ):
        if value[key] != job[key]:
            raise ValueError("ROBUSTNESS_RESULT_IDENTITY_CHANGED")
    record = value["artifact"]
    if set(record) != {"path", "sha256", "bytes"} or record["path"] != "periods.json":
        raise ValueError("INVALID_ROBUSTNESS_ARTIFACT")
    periods_path = safe_path(path.parent / "periods.json")
    if (
        periods_path.stat().st_size != record["bytes"]
        or digest(periods_path) != record["sha256"]
    ):
        raise ValueError("ROBUSTNESS_PERIODS_CHANGED")
    periods = read_json(periods_path)
    if (
        periods["schema"] != "competition.strategy_robustness_periods.v1"
        or periods["job_id"] != job["job_id"]
        or periods["plan_sha256"] != job["plan_sha256"]
    ):
        raise ValueError("INVALID_ROBUSTNESS_PERIODS")
    internal_job = job["input_job"] | {
        "job_id": job["job_id"],
        "products": job["products"],
        "fee_bps": job["fee_bps"],
    }
    internal = dict(
        schema="competition.daily_study_periods.v2",
        job_id=job["job_id"],
        net=periods["net"],
        gross=periods["gross"],
    )
    _verify_period_metrics(internal_job, value, internal)
    from .reference import (
        reference_account,
        compare_periods,
        input_prices,
        reference_targets,
    )

    full = input_prices(job)
    expected_prices = dict(
        dates=full["dates"][251:], close={p: v[251:] for p, v in full["close"].items()}
    )
    if periods["prices"] != expected_prices:
        raise ValueError("REFERENCE_PRICE_SLICE_MISMATCH")
    expected_targets = reference_targets(job, full)
    if len(expected_targets) != len(periods["targets"]) or any(
        set(a) != set(b)
        or any(
            not isinstance(b[p], (int, float)) or abs(v - b[p]) > 1e-10
            for p, v in a.items()
        )
        for a, b in zip(expected_targets, periods["targets"], strict=True)
    ):
        raise ValueError("REFERENCE_POLICY_MISMATCH")

    compare_periods(
        reference_account(
            periods["prices"], periods["targets"], fee_bps=job["fee_bps"]
        ),
        periods["net"],
    )
    compare_periods(
        reference_account(periods["prices"], periods["targets"], fee_bps=0),
        periods["gross"],
    )
    if job["market"] == "US":
        benchmark = periods["benchmark_periods"]
        spy = input_prices(job, benchmark=True)
        if benchmark["prices"] != dict(
            dates=spy["dates"][251:], close={"SPY": spy["close"]["SPY"][251:]}
        ) or benchmark["targets"] != [{"SPY": 1.0} for _ in spy["dates"][252:]]:
            raise ValueError("REFERENCE_BENCHMARK_SLICE_MISMATCH")
        for key, fee in (("net", job["fee_bps"]), ("gross", 0)):
            compare_periods(
                reference_account(
                    benchmark["prices"], benchmark["targets"], fee_bps=fee
                ),
                benchmark[key],
            )
        _verify_period_metrics(
            internal_job | {"products": ["SPY"]},
            {"metrics": value["benchmark"]},
            internal | {"net": benchmark["net"], "gross": benchmark["gross"]},
        )
        if (
            abs(value["benchmark"]["net_return"] - (benchmark["net"][-1]["equity"] - 1))
            > 1e-10
            or abs(
                value["benchmark"]["gross_return"]
                - (benchmark["gross"][-1]["equity"] - 1)
            )
            > 1e-10
        ):
            raise ValueError("REFERENCE_BENCHMARK_MISMATCH")
    if before != digest(path) or digest(periods_path) != record["sha256"]:
        raise ValueError("ROBUSTNESS_RESULT_CHANGED")
    return value
