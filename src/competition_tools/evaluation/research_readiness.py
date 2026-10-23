"""Allowlisted execution and observation status, without private data locators."""

import re
from datetime import datetime, timezone
from pathlib import Path

from ..datasets.daily_storage import safe_path
from ..datasets.storage import digest
from .controls.contracts import read_json
from .observation_registry import _protocol, inspect_observation, utc_time

CODES = {
    "USD_QUOTE_DECLARED",
    "US_MARKET_DECLARED",
    "RAW_EXECUTION_PRICES_REQUIRED",
    "FIRST_REGULAR_OPEN_EVIDENCE_UNVERIFIED",
    "AVAILABILITY_EVIDENCE_UNVERIFIED",
    "CORPORATE_ACTION_MODEL_UNVERIFIED",
    "LOT_AND_LISTING_EVIDENCE_UNVERIFIED",
}


def validate_public_readiness(value):
    try:
        if (
            set(value) != {"schema", "as_of", "code_commit", "execution", "observation"}
            or value["schema"] != "competition.public_strategy_evidence_readiness.v1"
            or not re.fullmatch(r"[a-f0-9]{40}", value["code_commit"])
        ):
            raise ValueError
        as_of = utc_time(value["as_of"])
        execution, observation = value["execution"], value["observation"]
        if (
            set(execution)
            != {
                "status",
                "model_id",
                "datasets_checked",
                "blockers",
                "return_basis",
                "orders_submitted",
                "total_return",
                "execution_eligible",
                "receipt_sha256",
            }
            or execution["status"] != "blocked"
            or execution["model_id"] != "us-next-session-price-nav.v1"
            or execution["return_basis"] != "usd_price_nav"
            or type(execution["orders_submitted"]) is not int
            or execution["orders_submitted"] != 0
            or execution["total_return"] is not False
            or execution["execution_eligible"] is not False
        ):
            raise ValueError
        if (
            type(execution["datasets_checked"]) is not int
            or not 1 <= execution["datasets_checked"] <= 16
            or not isinstance(execution["blockers"], list)
            or not execution["blockers"]
            or len(execution["blockers"]) != len(set(execution["blockers"]))
            or set(execution["blockers"]) - CODES
            or not re.fullmatch(r"[a-f0-9]{64}", execution["receipt_sha256"])
        ):
            raise ValueError
        if (
            set(observation)
            != {
                "schema",
                "protocol_id",
                "status",
                "freeze_at",
                "first_eligible_observation_at",
                "observations",
                "evidence_tier",
                "execution_authorized",
            }
            or observation["schema"] != "competition.observation_status.v1"
            or not re.fullmatch(r"[a-f0-9]{64}", observation["protocol_id"])
            or observation["execution_authorized"] is not False
            or type(observation["observations"]) is not int
            or observation["observations"] < 0
            or utc_time(observation["freeze_at"]) > as_of
        ):
            raise ValueError
        if observation["status"] == "awaiting_new_data":
            if (
                observation["observations"] != 0
                or observation["first_eligible_observation_at"] is not None
                or observation["evidence_tier"] != "readiness_only"
            ):
                raise ValueError
        elif observation["status"] == "observing":
            if (
                observation["observations"] == 0
                or observation["evidence_tier"] != "valuation_only"
                or not utc_time(observation["freeze_at"])
                < utc_time(observation["first_eligible_observation_at"])
                <= as_of
            ):
                raise ValueError
        else:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("INVALID_PUBLIC_RESEARCH_READINESS") from None
    return value


def build_public_readiness(execution_path: Path, registry_root: Path):
    source = safe_path(execution_path)
    before = digest(source)
    report = read_json(source)
    if (
        set(report)
        != {
            "schema",
            "status",
            "scope",
            "datasets",
            "model_id",
            "return_basis",
            "orders_submitted",
            "execution_eligible",
            "total_return",
        }
        or report["schema"] != "competition.us_execution_readiness.v1"
        or report["scope"] != "cached_daily_manifest_evidence_inventory"
    ):
        raise ValueError("INVALID_EXECUTION_READINESS_RECEIPT")
    blockers = set()
    for dataset in report["datasets"]:
        if (
            set(dataset) != {"manifest_sha256", "checks"}
            or not re.fullmatch(r"[a-f0-9]{64}", dataset["manifest_sha256"])
            or not isinstance(dataset["checks"], list)
            or len(dataset["checks"]) != len(CODES)
        ):
            raise ValueError("INVALID_EXECUTION_READINESS_RECEIPT")
        seen = set()
        for check in dataset["checks"]:
            if (
                set(check) != {"code", "status"}
                or check["code"] not in CODES
                or check["code"] in seen
                or check["status"] not in {"passed", "blocked"}
            ):
                raise ValueError("INVALID_EXECUTION_READINESS_RECEIPT")
            seen.add(check["code"])
            if check["status"] == "blocked":
                blockers.add(check["code"])
    protocol = _protocol(registry_root)
    if protocol["template"]["synthetic"]:
        raise ValueError("SYNTHETIC_REGISTRY_NOT_REAL_READINESS")
    observation = inspect_observation(registry_root)
    value = dict(
        schema="competition.public_strategy_evidence_readiness.v1",
        as_of=datetime.now(timezone.utc).isoformat(),
        code_commit=protocol["template"]["source_identity"]["commit"],
        execution={
            k: report[k]
            for k in (
                "status",
                "model_id",
                "return_basis",
                "orders_submitted",
                "execution_eligible",
                "total_return",
            )
        }
        | dict(
            datasets_checked=len(report["datasets"]),
            blockers=sorted(blockers),
            receipt_sha256=before,
        ),
        observation=observation,
    )
    if digest(source) != before or inspect_observation(registry_root) != observation:
        raise ValueError("READINESS_CHANGED_DURING_PROJECTION")
    return validate_public_readiness(value)
