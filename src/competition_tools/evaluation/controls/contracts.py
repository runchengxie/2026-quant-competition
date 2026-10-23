"""Strict, finite controls contracts without research-package dependencies."""

import json
import re
from datetime import date
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ..study_identity import canonical_hash
from .catalog import ARMS, BUDGET, COSTS, CATALOG_SHA256, arm_spec

SPEC_KEYS = {
    "schema",
    "manifests",
    "expected_input_hashes",
    "arms",
    "costs",
    "role",
    "accepted_research",
    "budget",
}
JOB_KEYS = {
    "schema",
    "market",
    "project",
    "arm_id",
    "parameters",
    "evidence_role",
    "catalog_sha256",
    "products",
    "benchmark",
    "quote_currency",
    "dates",
    "fold",
    "manifest",
    "manifest_sha256",
    "input_files",
    "input_slice",
    "expected_leaf_sha256",
    "fee_bps",
    "accounting_model",
    "execution_assumption",
    "accepted_research",
    "code_commit",
    "job_id",
    "plan_sha256",
}


def is_hash(value, length=64):
    return (
        isinstance(value, str)
        and re.fullmatch("[a-f0-9]{" + str(length) + "}", value) is not None
    )


def read_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("NONFINITE_JSON")

    value = json.loads(
        safe_path(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=pairs,
        parse_constant=nonfinite,
    )
    json.dumps(value, allow_nan=False)
    return value


def validate_spec(value: dict) -> dict:
    try:
        if not isinstance(value, dict) or set(value) != SPEC_KEYS:
            raise ValueError
        if (
            value["schema"] != "competition.strategy_controls_spec.v1"
            or value["role"] != "retrospective"
            or value["accepted_research"] is not False
        ):
            raise ValueError
        for field in ("manifests", "expected_input_hashes", "arms", "costs"):
            if not isinstance(value[field], dict) or set(value[field]) != set(ARMS):
                raise ValueError
        for market in ARMS:
            safe_path(Path(value["manifests"][market]))
            if not is_hash(value["expected_input_hashes"][market]):
                raise ValueError
            if (
                value["arms"][market] != ARMS[market]
                or value["costs"][market] != COSTS[market]
                or any(type(f) is not int for f in value["costs"][market])
            ):
                raise ValueError
        if value["budget"] != BUDGET or any(
            type(n) is not int for n in value["budget"].values()
        ):
            raise ValueError
        canonical_hash(value)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("INVALID_CONTROLS_SPEC") from None
    return value


def load_spec(path: Path) -> dict:
    return validate_spec(read_json(path))


def job_hash(job: dict) -> str:
    return canonical_hash(
        {k: v for k, v in job.items() if k not in {"job_id", "plan_sha256"}}
    )


def plan_hash(plan: dict) -> str:
    value = {k: v for k, v in plan.items() if k != "plan_sha256"}
    value["jobs"] = [
        {k: v for k, v in j.items() if k != "plan_sha256"} for j in plan["jobs"]
    ]
    return canonical_hash(value)


def validate_job(value: dict) -> dict:
    try:
        if (
            not isinstance(value, dict)
            or set(value) != JOB_KEYS
            or value["schema"] != "competition.strategy_controls_job.v1"
        ):
            raise ValueError
        market = value["market"]
        policy = arm_spec(market, value["arm_id"])
        if (
            canonical_hash(value["parameters"]) != canonical_hash(policy["parameters"])
            or value["evidence_role"] != policy["role"]
            or value["catalog_sha256"] != CATALOG_SHA256
            or value["accepted_research"] is not False
        ):
            raise ValueError
        if value["project"] != (
            "equity-lab" if market == "US" else "crypto-mm"
        ) or value["quote_currency"] != ("USD" if market == "US" else "USDT"):
            raise ValueError
        if type(value["fee_bps"]) is not int or value["fee_bps"] not in COSTS[market]:
            raise ValueError
        if (
            value["accounting_model"] != "self_financing_daily.v1"
            or value["execution_assumption"] != "lagged_close_proxy"
        ):
            raise ValueError
        for key in ("manifest_sha256", "expected_leaf_sha256", "plan_sha256", "job_id"):
            if not is_hash(value[key]):
                raise ValueError
        if not is_hash(value["code_commit"], 40) or value["job_id"] != job_hash(value):
            raise ValueError
        products, dates, fold = value["products"], value["dates"], value["fold"]
        if (
            not isinstance(products, list)
            or not 1 <= len(products) <= (10 if market == "US" else 20)
            or len(set(products)) != len(products)
            or any(not isinstance(p, str) or not p for p in products)
        ):
            raise ValueError
        if (
            not isinstance(dates, list)
            or dates != sorted(set(dates))
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
        ):
            raise ValueError
        score = 63 if market == "US" else 90
        if (
            set(fold)
            != {"warmup_start", "start", "end", "warmup_periods", "scoring_periods"}
            or type(fold["warmup_periods"]) is not int
            or type(fold["scoring_periods"]) is not int
            or fold["warmup_periods"] != 252
            or fold["scoring_periods"] != score
            or len(dates) != 252 + score
        ):
            raise ValueError
        if (fold["warmup_start"], fold["start"], fold["end"]) != (
            dates[0],
            dates[252],
            dates[-1],
        ):
            raise ValueError
        safe_path(Path(value["manifest"]))
        canonical_hash(value)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ValueError("INVALID_CONTROLS_JOB") from None
    return value
