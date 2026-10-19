"""Check offline experiment evidence without connecting to a broker or issuer."""

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from competition_tools.research_acceptance import (
    check_receipt_files,
    input_issues,
    read_json,
    validate_input_receipt,
)

SCHEMA = "competition.experiment_acceptance.v1"
PLAN_KEYS = {
    "schema_version",
    "purpose",
    "evaluation_kind",
    "strategy_id",
    "config",
    "config_fingerprint",
    "input_fingerprint",
    "output_fingerprint",
    "sample_interval",
    "windows",
    "minimum_universe",
    "minimum_observations",
    "costs",
    "history_exposed",
    "owner_protocol_receipt",
}
PUBLIC_KEYS = {
    "schema_version",
    "status",
    "purpose",
    "issue_codes",
    "input_fingerprint",
    "config_fingerprint",
    "output_fingerprint",
    "sample_counts",
}
ISSUE_CODES = set(
    """
SYNTHETIC_INPUT UNVERIFIED_AVAILABILITY UNKNOWN_TIMEZONE UNKNOWN_PRICE_BASIS
OWNER_PROVENANCE_UNVERIFIED INPUT_QUALITY_FAILED CONFIG_FINGERPRINT_MISMATCH
INPUT_FINGERPRINT_MISMATCH OUTPUT_FINGERPRINT_MISMATCH STRATEGY_MISMATCH
RUN_NOT_COMPLETED FALLBACK_USED NO_POSITIONS NO_ELIGIBLE_FOLDS WINDOW_OVERLAP
INSUFFICIENT_UNIVERSE INSUFFICIENT_OBSERVATIONS EMPTY_EVALUATION
OBSERVATION_OUTSIDE_SAMPLE DUPLICATE_OBSERVATION UNKNOWN_PNL_UNIT
RETURN_WITHOUT_CAPITAL UNKNOWN_CURRENCY UNVERIFIED_COSTS IN_SAMPLE_MODEL
OWNER_CONTRACT_VALIDATION_UNAVAILABLE EXPOSED_HISTORY RETROSPECTIVE_EVALUATION
UNKNOWN_UNIVERSE EMPTY_METRICS FILE_CHANGED FILE_UNAVAILABLE UNSAFE_FILE_REFERENCE
DATASET_ROOT_UNAVAILABLE
""".split()
)


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _number(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("INVALID_NUMBER")
    return float(value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    return datetime.fromisoformat(value)


def _window(value: object) -> tuple[datetime, datetime]:
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        raise ValueError("INVALID_WINDOW")
    start, end = _timestamp(value["start"]), _timestamp(value["end"])
    if start > end:
        raise ValueError("INVALID_WINDOW")
    return start, end


def _validate_plan(plan: dict) -> tuple[tuple, dict]:
    if (
        not isinstance(plan, dict)
        or set(plan) != PLAN_KEYS
        or plan["schema_version"] != "competition.experiment_plan.v1"
    ):
        raise ValueError("INVALID_EXPERIMENT_PLAN")
    if plan["purpose"] not in ("software_diagnostic", "research_evidence") or plan[
        "evaluation_kind"
    ] not in ("retrospective", "owner_unexposed"):
        raise ValueError("INVALID_PURPOSE")
    if not isinstance(plan["strategy_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", plan["strategy_id"]
    ):
        raise ValueError("INVALID_STRATEGY")
    for key in ("input_fingerprint", "config_fingerprint", "output_fingerprint"):
        if not isinstance(plan[key], str) or not re.fullmatch(
            r"[0-9a-f]{64}", plan[key]
        ):
            raise ValueError("INVALID_FINGERPRINT")
    for key in ("minimum_universe", "minimum_observations"):
        if type(plan[key]) is not int or plan[key] < 1:
            raise ValueError("INVALID_SAMPLE_MINIMUM")
    if type(plan["history_exposed"]) is not bool or not isinstance(
        plan["config"], dict
    ):
        raise ValueError("INVALID_PLAN_METADATA")
    if plan["owner_protocol_receipt"] is not None and not isinstance(
        plan["owner_protocol_receipt"], dict
    ):
        raise ValueError("INVALID_OWNER_REFERENCE")
    costs = plan["costs"]
    if not isinstance(costs, dict) or set(costs) != {
        "fee_bps",
        "slippage_bps",
        "currency",
        "verified",
    }:
        raise ValueError("INVALID_COSTS")
    _number(
        costs["fee_bps"]
    )  # Negative maker rebates are permitted, never implicitly verified.
    if (
        _number(costs["slippage_bps"]) < 0
        or type(costs["verified"]) is not bool
        or costs["currency"] not in ("HKD", "USD", "USDT", "USDC", "unknown")
    ):
        raise ValueError("INVALID_COSTS")
    sample = _window(plan["sample_interval"])
    windows = plan["windows"]
    if (
        not isinstance(windows, dict)
        or set(windows) != {"training", "validation", "evaluation"}
        or windows["evaluation"] is None
    ):
        raise ValueError("INVALID_WINDOWS")
    parsed = {
        key: _window(value) for key, value in windows.items() if value is not None
    }
    if any(start < sample[0] or end > sample[1] for start, end in parsed.values()):
        raise ValueError("WINDOW_OUTSIDE_SAMPLE")
    return sample, parsed


def assess_experiment(
    plan: dict, input_receipt: dict, summary: dict, observations: list[dict]
) -> dict:
    """Inspect supplied evidence; owner-governed research promotion is unavailable."""
    sample, windows = _validate_plan(plan)
    source = validate_input_receipt(input_receipt)
    if (
        not isinstance(summary, dict)
        or not isinstance(observations, list)
        or not all(isinstance(row, dict) for row in observations)
    ):
        raise ValueError("INVALID_EXPERIMENT_OUTPUT")
    actual_config = canonical_digest(plan["config"])
    actual_output = canonical_digest({"summary": summary, "observations": observations})
    issues = set(input_issues(source)) & ISSUE_CODES
    if source["quality"]["issue_codes"]:
        issues.add("INPUT_QUALITY_FAILED")
    blockers = set()
    for key, actual in (
        ("config_fingerprint", actual_config),
        ("input_fingerprint", source["fingerprint"]),
        ("output_fingerprint", actual_output),
    ):
        if plan[key] != actual:
            blockers.add(key.upper() + "_MISMATCH")
    if summary.get("strategy_id", summary.get("strategy")) != plan["strategy_id"]:
        blockers.add("STRATEGY_MISMATCH")
    crypto = source["market"] == "CRYPTO"
    if "positions_rows" in summary and (
        type(summary["positions_rows"]) is not int
        or summary["positions_rows"] != len(observations)
    ):
        raise ValueError("OBSERVATION_COUNT_MISMATCH")
    if summary.get("run_status", "completed" if crypto else None) != "completed":
        blockers.add("RUN_NOT_COMPLETED")
    if summary.get("fallback_reasons"):
        blockers.add("FALLBACK_USED")
    pairs = list(windows.values())
    if any(
        max(a[0], b[0]) <= min(a[1], b[1])
        for i, a in enumerate(pairs)
        for b in pairs[i + 1 :]
    ):
        blockers.add("WINDOW_OVERLAP")
    evaluation = windows["evaluation"]
    dates, codes, active, folds, seen = set(), set(), 0, set(), set()
    for row in observations:
        stamp = _timestamp(row.get("date", row.get("datetime")))
        if stamp < sample[0] or stamp > sample[1]:
            blockers.add("OBSERVATION_OUTSIDE_SAMPLE")
        if not evaluation[0] <= stamp <= evaluation[1]:
            continue
        code = (
            row.get("code")
            if not crypto
            else row.get("instrument", "unverified_instrument")
        )
        if not isinstance(code, str) or not code:
            raise ValueError("INVALID_INSTRUMENT")
        if not crypto and not code.startswith(source["market"] + "."):
            raise ValueError("MARKET_MISMATCH")
        key = (stamp, code)
        if key in seen:
            blockers.add("DUPLICATE_OBSERVATION")
        seen.add(key)
        dates.add(stamp)
        codes.add(code)
        weight = row.get("inventory") if crypto else row.get("target_weight")
        active += int(abs(_number(weight)) > 0)
        fold = row.get("cnn_walk_forward_fold")
        if fold is not None and fold != "":
            value = _number(fold)
            if value < 0 or not value.is_integer():
                raise ValueError("INVALID_FOLD")
            folds.add(int(value))
        if row.get("cnn_fallback_reason") or row.get("cnn_model_status") in (
            "fallback",
            "no_prediction",
        ):
            blockers.add("FALLBACK_USED")
    if not dates:
        blockers.add("EMPTY_EVALUATION")
    if len(dates) < plan["minimum_observations"]:
        blockers.add("INSUFFICIENT_OBSERVATIONS")
    if len(codes) < plan["minimum_universe"]:
        blockers.add("INSUFFICIENT_UNIVERSE")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        blockers.add("EMPTY_METRICS")
        metrics = {}
    if crypto:
        for key in (
            "total_pnl",
            "fee_cashflow",
            "max_absolute_inventory",
            "fill_count",
        ):
            if key not in metrics:
                blockers.add("EMPTY_METRICS")
            else:
                value = _number(metrics[key])
                if key in ("fill_count", "max_absolute_inventory") and value < 0:
                    raise ValueError("INVALID_CRYPTO_METRIC")
                if key == "fill_count" and not value.is_integer():
                    raise ValueError("INVALID_CRYPTO_METRIC")
        if summary.get("pnl_unit") not in (
            "HKD",
            "USD",
            "USDT",
            "USDC",
            "quote_currency",
        ):
            blockers.add("UNKNOWN_PNL_UNIT")
        if "total_return" in metrics and (
            summary.get("funded_capital") is None
            or _number(summary["funded_capital"]) <= 0
        ):
            blockers.add("RETURN_WITHOUT_CAPITAL")
        if not metrics.get("fill_count"):
            blockers.add("NO_POSITIONS")
    else:
        if metrics.get("total_return") is None:
            blockers.add("EMPTY_METRICS")
        else:
            _number(metrics["total_return"])
        if not active:
            blockers.add("NO_POSITIONS")
    if plan["strategy_id"] == "cnn_walk_forward_rank" and not folds:
        blockers.add("NO_ELIGIBLE_FOLDS")
    if plan["strategy_id"] in ("cnn_image_pattern", "cnn_pattern_mvp"):
        issues.add("IN_SAMPLE_MODEL")
    if plan["purpose"] == "research_evidence":
        blockers.update(issues)
        blockers.add("OWNER_CONTRACT_VALIDATION_UNAVAILABLE")
        if plan["history_exposed"]:
            blockers.add("EXPOSED_HISTORY")
        if plan["evaluation_kind"] == "retrospective":
            blockers.add("RETROSPECTIVE_EVALUATION")
        if source["universe_state"] != "point_in_time":
            blockers.add("UNKNOWN_UNIVERSE")
        if not plan["costs"]["verified"]:
            blockers.add("UNVERIFIED_COSTS")
        if plan["costs"]["currency"] == "unknown":
            blockers.add("UNKNOWN_CURRENCY")
    if "INPUT_QUALITY_FAILED" in issues:
        blockers.add("INPUT_QUALITY_FAILED")
    return {
        "schema_version": SCHEMA,
        "status": "blocked" if blockers else "accepted_diagnostic",
        "purpose": plan["purpose"],
        "issue_codes": sorted(issues | blockers),
        "input_fingerprint": source["fingerprint"],
        "config_fingerprint": actual_config,
        "output_fingerprint": actual_output,
        "sample_counts": {
            "observations": len(dates),
            "universe": len(codes),
            "active_observations": active,
            "folds": len(folds),
        },
    }


def public_acceptance_summary(receipt: dict) -> dict:
    """Validate the entire aggregate allowlist before a separate publication step."""
    if (
        not isinstance(receipt, dict)
        or set(receipt) != PUBLIC_KEYS
        or receipt["schema_version"] != SCHEMA
    ):
        raise ValueError("INVALID_PUBLIC_RECEIPT")
    if receipt["status"] not in ("blocked", "accepted_diagnostic") or receipt[
        "purpose"
    ] not in ("software_diagnostic", "research_evidence"):
        raise ValueError("INVALID_PUBLIC_STATUS")
    codes = receipt["issue_codes"]
    if (
        not isinstance(codes, list)
        or any(not isinstance(code, str) or code not in ISSUE_CODES for code in codes)
        or codes != sorted(set(codes))
    ):
        raise ValueError("INVALID_PUBLIC_ISSUES")
    for key in ("input_fingerprint", "config_fingerprint", "output_fingerprint"):
        if not isinstance(receipt[key], str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt[key]
        ):
            raise ValueError("INVALID_PUBLIC_FINGERPRINT")
    counts = receipt["sample_counts"]
    if (
        not isinstance(counts, dict)
        or set(counts) != {"observations", "universe", "active_observations", "folds"}
        or any(type(n) is not int or n < 0 for n in counts.values())
    ):
        raise ValueError("INVALID_PUBLIC_COUNTS")
    if (
        receipt["status"] == "accepted_diagnostic"
        and receipt["purpose"] != "software_diagnostic"
    ):
        raise ValueError("INVALID_PUBLIC_STATUS")
    return json.loads(json.dumps(receipt, allow_nan=False))


def _observations(path: Path) -> list[dict]:
    if path.suffix.lower() != ".csv":
        value = read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise ValueError("INVALID_OBSERVATIONS")
        return value
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in ("target_weight", "inventory", "cnn_walk_forward_fold"):
            if key in row and row[key] != "":
                row[key] = float(row[key])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in (
        "plan",
        "input-receipt",
        "summary",
        "observations",
        "dataset-root",
        "output",
    ):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    try:
        source = validate_input_receipt(read_json(args.input_receipt))
        plan, summary = read_json(args.plan), read_json(args.summary)
        if not isinstance(plan, dict) or not isinstance(summary, dict):
            raise ValueError("INVALID_EXPERIMENT_OUTPUT")
        result = assess_experiment(
            plan,
            source,
            summary,
            _observations(args.observations),
        )
        changed = check_receipt_files(source, args.dataset_root)
        if changed:
            result["status"] = "blocked"
            result["issue_codes"] = sorted(set(result["issue_codes"]) | set(changed))
        public_acceptance_summary(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps(result, allow_nan=False))
        return 2 if result["status"] == "blocked" else 0
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["INVALID_EXPERIMENT_EVIDENCE"]}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
