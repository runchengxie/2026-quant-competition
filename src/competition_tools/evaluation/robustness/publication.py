"""Exact reviewed aggregate releases; raw licensed bars never enter the site."""

from datetime import datetime, timezone
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest
from ..controls.contracts import read_json, is_hash
from ..controls.verification import verify_control_result
from ..study_identity import canonical_hash
from .plan import verify_plan
from .verification import verify_robustness_result

# Exact owner-authorized aggregate release. Private evidence stays external.
TRUSTED_PUBLICATION_REVIEWS = frozenset(
    {"c0c912dc8a738c95849c89102446f26f7a772aeea3fa367b6a68eaea54285db0"}
)
REVIEWED_PUBLIC_ROBUSTNESS = frozenset(
    {"7fadae43bdafc0c445ee5fbea2b1ec369cdd400a6ffabb2bb24544d756baf2dd"}
)
RESTRICTIONS = [
    "retrospective_diagnostic",
    "fixed_current_pools",
    "selection_bias",
    "independent_cash_windows",
    "lagged_close_proxy",
    "no_terminal_liquidation",
    "US_split_adjusted_not_total_return",
    "USDT_not_USD",
    "final_volume_ex_post_only",
    "no_spread_or_orderbook_evidence",
    "not_execution_authorization",
]
KEYS = set(
    "schema status as_of code_commit plan_sha256 coverage results us_pairs crypto_pairs capacity blockers restrictions".split()
)


def permission_verified(value, *, plan_sha256: str, results_sha256: str) -> bool:
    try:
        if (
            set(value)
            != set(
                "schema scope plan_sha256 results_sha256 evidence_file evidence_sha256 decision reviewed_at".split()
            )
            or value["schema"]
            != "competition.strategy_robustness_publication_review.v1"
            or value["scope"] != "derived_strategy_statistics"
            or value["decision"] != "permitted"
            or value["plan_sha256"] != plan_sha256
            or value["results_sha256"] != results_sha256
        ):
            return False
        signature = canonical_hash(
            {k: v for k, v in value.items() if k != "evidence_file"}
        )
        time = datetime.fromisoformat(value["reviewed_at"].replace("Z", "+00:00"))
        return (
            signature in TRUSTED_PUBLICATION_REVIEWS
            and time.tzinfo is not None
            and time <= datetime.now(timezone.utc)
            and digest(safe_path(Path(value["evidence_file"])))
            == value["evidence_sha256"]
        )
    except (ValueError, TypeError, KeyError, OSError):
        return False


def validate_public_robustness(value: dict) -> dict:
    try:
        if (
            set(value) != KEYS
            or value["schema"] != "competition.public_strategy_robustness.v1"
            or value["status"] not in {"measured", "readiness_only"}
            or value["restrictions"] != RESTRICTIONS
        ):
            raise ValueError
        canonical_hash(value)  # Reject non-finite numbers before rendering.
        if not is_hash(value["code_commit"], 40) or not is_hash(value["plan_sha256"]):
            raise ValueError
        as_of = datetime.fromisoformat(value["as_of"].replace("Z", "+00:00"))
        if as_of.tzinfo is None or as_of > datetime.now(timezone.utc):
            raise ValueError
        for key in ("results", "us_pairs", "crypto_pairs", "capacity", "blockers"):
            if not isinstance(value[key], list):
                raise ValueError
        if any(
            b
            not in {
                "PUBLICATION_PERMISSION_UNVERIFIED",
                "INCOMPLETE_ROBUSTNESS_RUN",
                "INCOMPLETE_CAPACITY_RUN",
            }
            for b in value["blockers"]
        ):
            raise ValueError
        coverage = value["coverage"]
        if (
            set(coverage)
            != set(
                "requested_jobs completed_jobs blocked_jobs requested_capacity_checks completed_capacity_checks".split()
            )
            or any(type(n) is not int or n < 0 for n in coverage.values())
            or coverage["requested_jobs"] != 114
            or coverage["requested_capacity_checks"] != 288
            or coverage["completed_jobs"] + coverage["blocked_jobs"] != 114
            or coverage["completed_capacity_checks"] > 288
        ):
            raise ValueError
        if value["status"] == "measured":
            if (
                canonical_hash(value) not in REVIEWED_PUBLIC_ROBUSTNESS
                or len(value["results"]) != 114
            ):
                raise ValueError
        elif any(value[k] for k in ("results", "us_pairs", "crypto_pairs", "capacity")):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError("UNREVIEWED_OR_INVALID_PUBLIC_ROBUSTNESS") from None
    return value


def review_candidate(plan_path: Path, results_path: Path) -> dict:
    """Build private review material. The site gate rejects unregistered hashes."""
    plan = verify_plan(plan_path)
    before = digest(safe_path(results_path))
    results = read_json(results_path)
    if (
        results["schema"] != "competition.strategy_robustness_results.v1"
        or results["plan_sha256"] != plan["plan_sha256"]
        or len(results["jobs"]) != 114
    ):
        raise ValueError("INVALID_ROBUSTNESS_RESULTS_INDEX")
    lookup = {j["job_id"]: j for j in plan["jobs"]}
    if {r["job_id"] for r in results["jobs"]} != set(lookup) or len(
        {r["job_id"] for r in results["jobs"]}
    ) != 114:
        raise ValueError("ROBUSTNESS_DENOMINATOR_CHANGED")
    rows, us_pairs = [], []
    for row in results["jobs"]:
        job = lookup[row["job_id"]]
        for key in ("market", "pool_id", "fee_bps"):
            if row[key] != job[key]:
                raise ValueError("ROBUSTNESS_INDEX_IDENTITY_CHANGED")
        base = job["input_job"]
        if (
            row["start"] != base["fold"]["start"]
            or row["end"] != base["fold"]["end"]
            or row["arm_id"] != base["arm_id"]
        ):
            raise ValueError("ROBUSTNESS_WINDOW_CHANGED")
        public = {
            k: row[k]
            for k in (
                "job_id",
                "market",
                "arm_id",
                "pool_id",
                "fee_bps",
                "start",
                "end",
                "status",
                "reason",
                "metrics",
                "benchmark",
            )
        }
        public["baseline_net_return"] = None
        if row["status"] == "completed":
            relative = Path(row["result_path"])
            if relative.is_absolute() or relative.parts != (
                job["market"],
                job["job_id"],
                "result.json",
            ):
                raise ValueError("INVALID_ROBUSTNESS_RESULT_PATH")
            actual = verify_robustness_result(
                job, safe_path(results_path.parent / relative)
            )
            if (
                actual["metrics"] != row["metrics"]
                or actual["benchmark"] != row["benchmark"]
            ):
                raise ValueError("ROBUSTNESS_SUMMARY_CHANGED")
            prior = verify_control_result(base, safe_path(Path(job["parent_result"])))
            public["baseline_net_return"] = prior["metrics"]["net_return"]
            if row["market"] == "US":
                us_pairs.append(
                    dict(
                        job_id=row["job_id"],
                        baseline_job_id=base["job_id"],
                        pool_id=row["pool_id"],
                        fee_bps=row["fee_bps"],
                        start=row["start"],
                        end=row["end"],
                        net_return_change=row["metrics"]["net_return"]
                        - prior["metrics"]["net_return"],
                        drawdown_change=row["metrics"]["max_drawdown"]
                        - prior["metrics"]["max_drawdown"],
                        spy_net_return_change=row["metrics"]["net_return"]
                        - row["benchmark"]["net_return"],
                    )
                )
        elif row["status"] != "blocked" or any(
            row[k] is not None for k in ("metrics", "benchmark", "result_path")
        ):
            raise ValueError("INVALID_BLOCKED_ROBUSTNESS_ROW")
        rows.append(public)
    crypto_pairs = []
    selected = {
        (r["arm_id"], r["fee_bps"], r["start"]): r
        for r in rows
        if r["market"] == "crypto" and r["status"] == "completed"
    }
    for (arm, fee, start), row in selected.items():
        if arm != "trend200_vol40_strict":
            continue
        other = selected.get(("ew_trend_gross_matched", fee, start))
        if other:
            crypto_pairs.append(
                dict(
                    candidate_job_id=row["job_id"],
                    control_job_id=other["job_id"],
                    fee_bps=fee,
                    start=start,
                    end=row["end"],
                    net_return_change=row["metrics"]["net_return"]
                    - other["metrics"]["net_return"],
                    drawdown_change=row["metrics"]["max_drawdown"]
                    - other["metrics"]["max_drawdown"],
                )
            )
    capacity = results["capacity"]
    expected = {
        (j["job_id"], n, t)
        for j in plan["jobs"]
        if j["market"] == "crypto"
        for n in (10000, 100000, 1000000)
        for t in (0.01, 0.05)
    }
    if len(capacity) != len(
        {(r["job_id"], r["notional_usdt"], r["threshold"]) for r in capacity}
    ) or any(
        (r["job_id"], r["notional_usdt"], r["threshold"]) not in expected
        or not r["ex_post"]
        or r["execution_eligible"]
        for r in capacity
    ):
        raise ValueError("INVALID_CAPACITY_DENOMINATOR")
    # Fixed public keys exclude raw trade quantities, volumes and input paths.
    capacity_keys = "job_id notional_usdt threshold status max_participation breach_days unavailable_days ex_post execution_eligible".split()
    if any(set(r) != set(capacity_keys) for r in capacity):
        raise ValueError("UNKNOWN_CAPACITY_PUBLIC_FIELD")
    complete = sum(r["status"] == "completed" for r in rows)
    value = dict(
        schema="competition.public_strategy_robustness.v1",
        status="measured",
        as_of=plan["frozen_at"],
        code_commit=plan["code_identity"]["commit"],
        plan_sha256=plan["plan_sha256"],
        coverage=dict(
            requested_jobs=114,
            completed_jobs=complete,
            blocked_jobs=114 - complete,
            requested_capacity_checks=288,
            completed_capacity_checks=len(capacity),
        ),
        results=rows,
        us_pairs=us_pairs,
        crypto_pairs=crypto_pairs,
        capacity=capacity,
        blockers=[] if complete == 114 else ["INCOMPLETE_ROBUSTNESS_RUN"],
        restrictions=RESTRICTIONS,
    )
    if before != digest(results_path):
        raise ValueError("ROBUSTNESS_RESULTS_CHANGED")
    return value


def build_public_robustness(
    plan_path: Path, results_path: Path, *, publication_review: dict
) -> dict:
    candidate = review_candidate(plan_path, results_path)
    if not permission_verified(
        publication_review,
        plan_sha256=candidate["plan_sha256"],
        results_sha256=digest(results_path),
    ):
        candidate.update(
            status="readiness_only",
            results=[],
            us_pairs=[],
            crypto_pairs=[],
            capacity=[],
            blockers=["PUBLICATION_PERMISSION_UNVERIFIED", *candidate["blockers"]],
        )
    return validate_public_robustness(candidate)
