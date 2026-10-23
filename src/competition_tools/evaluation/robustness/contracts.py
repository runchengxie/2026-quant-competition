"""New robustness identities wrap unchanged, validated historical input jobs."""

from pathlib import Path

from ...datasets.daily_storage import safe_path
from ..controls.contracts import is_hash, validate_job as validate_input_job
from ..study_identity import canonical_hash
from .catalog import CATALOG_SHA256, CRYPTO_ARMS, POOLS, STOCKS

SPEC_KEYS = set(
    "schema parent_plan parent_results expected_parent_plan_sha256 expected_parent_results_sha256 role accepted_research".split()
)
JOB_KEYS = set(
    "schema input_job parent_result parent_result_sha256 pool_id fee_bps market products expected_leaf_sha256 catalog_sha256 code_commit accepted_research job_id plan_sha256".split()
)


def validate_spec(value: dict) -> dict:
    if (
        set(value) != SPEC_KEYS
        or value["schema"] != "competition.strategy_robustness_spec.v1"
        or value["role"] != "retrospective_diagnostic"
        or value["accepted_research"] is not False
    ):
        raise ValueError("INVALID_ROBUSTNESS_SPEC")
    for key in ("parent_plan", "parent_results"):
        safe_path(Path(value[key]))
    if not all(
        is_hash(value[k])
        for k in ("expected_parent_plan_sha256", "expected_parent_results_sha256")
    ):
        raise ValueError("INVALID_ROBUSTNESS_PARENT_HASH")
    return value


def job_hash(value: dict) -> str:
    return canonical_hash(
        {k: v for k, v in value.items() if k not in {"job_id", "plan_sha256"}}
    )


def validate_job(value: dict) -> dict:
    if (
        set(value) != JOB_KEYS
        or value["schema"] != "competition.strategy_robustness_job.v1"
        or value["accepted_research"] is not False
        or value["catalog_sha256"] != CATALOG_SHA256
        or value["job_id"] != job_hash(value)
    ):
        raise ValueError("INVALID_ROBUSTNESS_JOB")
    base = validate_input_job(value["input_job"])
    if (
        value["market"] != base["market"]
        or type(value["fee_bps"]) is not int
        or not all(
            is_hash(value[k])
            for k in ("expected_leaf_sha256", "plan_sha256", "parent_result_sha256")
        )
        or not is_hash(value["code_commit"], 40)
    ):
        raise ValueError("INVALID_ROBUSTNESS_IDENTITY")
    safe_path(Path(value["parent_result"]))
    if value["market"] == "US":
        if (
            base["arm_id"] != "ew_monthly"
            or set(base["products"]) != STOCKS
            or value["pool_id"] not in POOLS
            or value["products"] != POOLS[value["pool_id"]]
            or value["fee_bps"] != base["fee_bps"]
        ):
            raise ValueError("INVALID_US_ROBUSTNESS_POOL_OR_FEE")
    elif value["market"] == "crypto":
        if (
            base["arm_id"] not in CRYPTO_ARMS
            or base["fee_bps"] != 25
            or value["pool_id"] != "existing_eight"
            or value["products"] != base["products"]
            or value["fee_bps"] not in (35, 50)
        ):
            raise ValueError("INVALID_CRYPTO_ROBUSTNESS_FEE")
    else:
        raise ValueError("UNSUPPORTED_ROBUSTNESS_MARKET")
    return value
