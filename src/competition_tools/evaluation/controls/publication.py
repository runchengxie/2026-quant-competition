"""Allowlisted controls summaries; publication trust is never caller-created."""

import argparse
import math
from datetime import datetime, date
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ..study_identity import canonical_hash
from .catalog import ARMS, COSTS, arm_spec
from ..ablation_runner import METRIC_KEYS
from .contracts import read_json, is_hash
from .verification import verify_plan, verify_control_result, validate_results_index

# Explicit reviewed evidence decisions may be added by reviewed source changes.
# There is no verified rights decision for this new result family yet.
TRUSTED_PUBLICATION_REVIEWS = frozenset()
REVIEWED_PUBLIC_CONTROLS = frozenset()
RESTRICTIONS = [
    "fixed_current_selection",
    "retrospective_not_untouched_oos",
    "lagged_close_proxy",
    "independent_cash_windows",
    "no_terminal_liquidation",
    "not_execution_authorization",
    "US_split_adjusted_not_total_return",
    "USDT_not_USD",
]
PUBLIC_KEYS = set(
    "schema status as_of code_commit plan_sha256 coverage methods results pairs blockers restrictions".split()
)


def permission_verified(value, *, plan_sha256, results_sha256):
    keys = set(
        "schema scope plan_sha256 results_sha256 evidence_file evidence_sha256 decision reviewed_at".split()
    )
    try:
        if (
            not isinstance(value, dict)
            or set(value) != keys
            or value["schema"] != "competition.strategy_controls_publication_review.v1"
            or value["scope"] != "derived_strategy_statistics"
            or value["decision"] != "permitted"
        ):
            return False
        if (
            value["plan_sha256"] != plan_sha256
            or value["results_sha256"] != results_sha256
            or not is_hash(value["evidence_sha256"])
        ):
            return False
        signature = canonical_hash(
            {k: v for k, v in value.items() if k != "evidence_file"}
        )
        if signature not in TRUSTED_PUBLICATION_REVIEWS:
            return False
        checked = datetime.fromisoformat(value["reviewed_at"].replace("Z", "+00:00"))
        evidence = safe_path(Path(value["evidence_file"]))
        return (
            checked.tzinfo is not None
            and evidence.is_file()
            and digest(evidence) == value["evidence_sha256"]
        )
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return False


def _validate_public_controls(value):
    if (
        not isinstance(value, dict)
        or set(value) != PUBLIC_KEYS
        or value["schema"] != "competition.public_strategy_controls.v1"
        or value["status"] not in {"readiness_only", "measured"}
        or value["restrictions"] != RESTRICTIONS
    ):
        raise ValueError("INVALID_PUBLIC_CONTROLS")
    if not is_hash(value["code_commit"], 40) or not is_hash(value["plan_sha256"]):
        raise ValueError("INVALID_PUBLIC_CONTROLS")
    if value["status"] == "readiness_only" and (value["results"] or value["pairs"]):
        raise ValueError("UNPERMITTED_CONTROLS_METRICS")
    coverage = value["coverage"]
    if (
        not isinstance(coverage, dict)
        or set(coverage) != {"requested_jobs", "completed_jobs", "blocked_jobs"}
        or any(type(n) is not int or n < 0 for n in coverage.values())
        or coverage["completed_jobs"] + coverage["blocked_jobs"]
        != coverage["requested_jobs"]
    ):
        raise ValueError("INVALID_CONTROLS_COVERAGE")
    allowed_methods = [
        {"market": m, **arm_spec(m, a)} for m, arms in ARMS.items() for a in arms
    ]
    if canonical_hash(value["methods"]) != canonical_hash(allowed_methods):
        raise ValueError("INVALID_PUBLIC_CONTROLS_METHODS")
    if not isinstance(value["blockers"], list) or any(
        x not in {"PUBLICATION_PERMISSION_UNVERIFIED", "INCOMPLETE_CONTROLS_RUN"}
        for x in value["blockers"]
    ):
        raise ValueError("INVALID_PUBLIC_CONTROLS_BLOCKERS")
    if value["status"] == "measured" and (
        value["blockers"] or len(value["results"]) != coverage["completed_jobs"]
    ):
        raise ValueError("INVALID_PUBLIC_CONTROLS_COVERAGE")
    timestamp = datetime.fromisoformat(value["as_of"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or not 1 <= coverage["requested_jobs"] <= 512:
        raise ValueError("INVALID_PUBLIC_CONTROLS_TIME_OR_COUNT")
    if not isinstance(value["results"], list) or not isinstance(value["pairs"], list):
        raise ValueError("INVALID_PUBLIC_CONTROLS_ROWS")
    identities, job_ids = set(), set()
    for row in value["results"]:
        if not isinstance(row, dict) or set(row) != {
            "job_id",
            "market",
            "arm_id",
            "fee_bps",
            "quote_currency",
            "start",
            "end",
            "metrics",
        }:
            raise ValueError("INVALID_PUBLIC_CONTROLS_ROW")
        market = row["market"]
        if (
            market not in ARMS
            or row["arm_id"] not in ARMS[market]
            or type(row["fee_bps"]) is not int
            or row["fee_bps"] not in COSTS[market]
            or row["quote_currency"] != ("USD" if market == "US" else "USDT")
            or not is_hash(row["job_id"])
        ):
            raise ValueError("INVALID_PUBLIC_CONTROLS_IDENTITY")
        start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
        if (
            start.isoformat() != row["start"]
            or end.isoformat() != row["end"]
            or start > end
            or end > timestamp.date()
        ):
            raise ValueError("INVALID_PUBLIC_CONTROLS_RANGE")
        identity = (market, row["arm_id"], row["fee_bps"], row["start"], row["end"])
        if identity in identities or row["job_id"] in job_ids:
            raise ValueError("DUPLICATE_PUBLIC_CONTROLS_ROW")
        identities.add(identity)
        job_ids.add(row["job_id"])
        metrics = row["metrics"]
        if not isinstance(metrics, dict) or set(metrics) != METRIC_KEYS:
            raise ValueError("INVALID_PUBLIC_CONTROLS_METRICS")
        for key, number in metrics.items():
            if key == "sharpe" and number is None:
                continue
            if type(number) not in (int, float) or not math.isfinite(number):
                raise ValueError("INVALID_PUBLIC_CONTROLS_NUMBER")
        if (
            type(metrics["periods"]) is not int
            or metrics["periods"] != (63 if market == "US" else 90)
            or type(metrics["flat_days"]) is not int
            or not 0 <= metrics["flat_days"] <= metrics["periods"]
        ):
            raise ValueError("INVALID_PUBLIC_CONTROLS_DENOMINATOR")
        if (
            any(
                metrics[k] < 0
                for k in (
                    "volatility",
                    "max_drawdown",
                    "turnover",
                    "total_costs",
                    "mean_daily_turnover",
                    "mean_exposure",
                )
            )
            or metrics["max_drawdown"] > 1
            or metrics["mean_exposure"] > 1 + 1e-12
            or min(metrics["net_return"], metrics["gross_return"]) < -1
        ):
            raise ValueError("INVALID_PUBLIC_CONTROLS_METRICS")
        if not math.isclose(
            metrics["gross_return"] - metrics["net_return"],
            metrics["cost_drag"],
            abs_tol=1e-10,
            rel_tol=0,
        ) or (metrics["volatility"] == 0) != (metrics["sharpe"] is None):
            raise ValueError("INVALID_PUBLIC_CONTROLS_METRICS")
    if canonical_hash(_pairs(value["results"])) != canonical_hash(value["pairs"]):
        raise ValueError("INVALID_PUBLIC_CONTROLS_PAIRS")
    if value["status"] == "readiness_only" and not value["blockers"]:
        raise ValueError("MISSING_CONTROLS_BLOCKER")
    canonical_hash(value)
    return value


def validate_public_controls(value):
    try:
        return _validate_public_controls(value)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ValueError("INVALID_PUBLIC_CONTROLS") from None


def _pairs(rows):
    lookup = {
        (r["market"], r["arm_id"], r["fee_bps"], r["start"], r["end"]): r for r in rows
    }
    comparisons = {
        "ew_monthly_buffer20": ["ew_monthly"],
        "mom20_monthly_buffer20": ["mom20_monthly"],
        "trend200_fixed60_legacy": ["trend200_legacy", "ew_fixed60"],
        "trend200_vol40_strict": [
            "trend200_legacy",
            "ew_vol40_strict",
            "ew_trend_gross_matched",
        ],
    }
    pairs = []
    for row in rows:
        for control in comparisons.get(row["arm_id"], []):
            other = lookup.get(
                (row["market"], control, row["fee_bps"], row["start"], row["end"])
            )
            if other is None:
                raise ValueError("MISSING_CONTROLS_PAIR")
            identity = dict(
                market=row["market"],
                fee_bps=row["fee_bps"],
                start=row["start"],
                end=row["end"],
                candidate_job_id=row["job_id"],
                control_job_id=other["job_id"],
            )
            pairs.append(
                identity
                | {
                    "pair_id": canonical_hash(identity),
                    "candidate_arm": row["arm_id"],
                    "control_arm": control,
                    "net_return_change": row["metrics"]["net_return"]
                    - other["metrics"]["net_return"],
                    "drawdown_change": row["metrics"]["max_drawdown"]
                    - other["metrics"]["max_drawdown"],
                    "turnover_change": row["metrics"]["mean_daily_turnover"]
                    - other["metrics"]["mean_daily_turnover"],
                    "exposure_change": row["metrics"]["mean_exposure"]
                    - other["metrics"]["mean_exposure"],
                }
            )
    return pairs


def build_public_controls(
    plan_path: Path, results_path: Path, *, publication_review: dict
) -> dict:
    plan = verify_plan(plan_path)
    results_path = safe_path(results_path)
    results_hash = digest(results_path)
    results = validate_results_index(plan, read_json(results_path))
    if (
        results["schema"] != "competition.strategy_controls_results.v1"
        or results["plan_sha256"] != plan["plan_sha256"]
        or len(results["jobs"]) != len(plan["jobs"])
    ):
        raise ValueError("INVALID_CONTROLS_RESULTS")
    lookup = {j["job_id"]: j for j in plan["jobs"]}
    seen, rows = set(), []
    for record in results["jobs"]:
        job = lookup[record["job_id"]]
        if job["job_id"] in seen:
            raise ValueError("DUPLICATE_CONTROLS_RESULT")
        seen.add(job["job_id"])
        if record["status"] != "completed":
            if record["metrics"] is not None:
                raise ValueError("BLOCKED_CONTROLS_METRICS")
            continue
        actual = verify_control_result(
            job, safe_path(results_path.parent / record["result_path"])
        )
        if canonical_hash(actual["metrics"]) != canonical_hash(record["metrics"]):
            raise ValueError("CONTROLS_SUMMARY_CHANGED")
        rows.append(
            dict(
                job_id=job["job_id"],
                market=job["market"],
                arm_id=job["arm_id"],
                fee_bps=job["fee_bps"],
                quote_currency=job["quote_currency"],
                start=job["fold"]["start"],
                end=job["fold"]["end"],
                metrics=actual["metrics"],
            )
        )
    allowed = permission_verified(
        publication_review, plan_sha256=plan["plan_sha256"], results_sha256=results_hash
    )
    complete = len(rows) == len(plan["jobs"]) and results["status"] == "completed"
    blockers = ([] if allowed else ["PUBLICATION_PERMISSION_UNVERIFIED"]) + (
        [] if complete else ["INCOMPLETE_CONTROLS_RUN"]
    )
    value = dict(
        schema="competition.public_strategy_controls.v1",
        status="measured" if not blockers else "readiness_only",
        as_of=plan["frozen_at"],
        code_commit=plan["code_commit"],
        plan_sha256=plan["plan_sha256"],
        coverage=dict(
            requested_jobs=len(plan["jobs"]),
            completed_jobs=len(rows),
            blocked_jobs=len(plan["jobs"]) - len(rows),
        ),
        methods=[
            {"market": m, **arm_spec(m, a)} for m, arms in ARMS.items() for a in arms
        ],
        results=rows if not blockers else [],
        pairs=_pairs(rows) if not blockers else [],
        blockers=blockers,
        restrictions=RESTRICTIONS,
    )
    if (
        digest(results_path) != results_hash
        or verify_plan(plan_path)["plan_sha256"] != plan["plan_sha256"]
    ):
        raise ValueError("CONTROLS_PROJECTION_CHANGED")
    return validate_public_controls(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "results", "review", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    value = build_public_controls(
        args.plan, args.results, publication_review=read_json(args.review)
    )
    target = safe_path(args.output)
    if target.exists():
        raise FileExistsError("PUBLIC_CONTROLS_OUTPUT_EXISTS")
    write_json(target, value)


if __name__ == "__main__":
    main()
