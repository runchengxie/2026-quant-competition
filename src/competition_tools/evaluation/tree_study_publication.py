"""Closed stdlib public contract; no private research inputs are needed to read it."""

import json
import math
import re
from itertools import product

from .study_identity import canonical_hash
from .tree_study import PROTOCOL, rules

REVIEWED_SHA256 = "cd5bff08818a3eca86d68a21b2a0bb8c67330ef6227792c87e0788f291631c28"
WINDOWS = dict(rules()["windows"])
COUNTS = dict(
    reused_requested_accounts=168,
    new_requested_accounts=96,
    fit_attempts=12,
    completed_new_accounts=60,
    blocked_new_accounts=36,
    ranking_pool_blocks=18,
    known_action_blocks=18,
    matched_comparisons=432,
)
PROVENANCE = "binding_sha256 input_sha256 parent_result_sha256 parent_plan_sha256 calendar_sha256 leaf_code_sha256 root_lock_sha256 equity_lock_sha256 report_sha256 verification_sha256 source_identity_sha256"
REASONS = {
    "INVALID_RANKING_POOL",
    "KNOWN_ACTION_BOUNDARY",
    "EMPTY_DECISION_POOL",
    "MODEL_UNAVAILABLE",
    "CONSTANT_SCORES",
    "MISSING_HELD_OR_SELECTED_PRICE",
}


def keys(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("TREE_PUBLIC_FIELDS_CHANGED")


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("TREE_PUBLIC_NONFINITE_NUMBER")


def count(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("TREE_PUBLIC_COUNT_CHANGED")


def validate(value):
    keys(
        value,
        "schema protocol retrospective formal_performance_ready scientific_requirements uncertainty rules provenance counts models comparisons",
    )
    if (
        value["schema"] != "competition.public_tree_study.v1"
        or value["protocol"] != PROTOCOL
        or value["retrospective"] is not True
        or value["formal_performance_ready"] is not False
        or value["scientific_requirements"] != "all_six_remain_blocked"
        or value["uncertainty"] != "unavailable_uncertainty_tooling_not_validated"
        or canonical_hash(value["rules"]) != canonical_hash(rules())
        or canonical_hash(value["counts"]) != canonical_hash(COUNTS)
    ):
        raise ValueError("TREE_PUBLIC_RULES_OR_COUNTS_CHANGED")
    keys(value["provenance"], PROVENANCE)
    if any(
        not isinstance(v, str) or not re.fullmatch("[0-9a-f]{64}", v)
        for v in value["provenance"].values()
    ):
        raise ValueError("TREE_PUBLIC_PROVENANCE_CHANGED")
    if not isinstance(value["models"], list) or len(value["models"]) != 8:
        raise ValueError("TREE_PUBLIC_MODEL_GRID_CHANGED")
    seen = set()
    for row in value["models"]:
        keys(
            row,
            "horizon window end model status requested_dates valid_ic_dates valid_mse_dates mean_daily_ic mean_daily_mse",
        )
        identity = row["horizon"], row["window"], row["model"]
        if (
            identity in seen
            or identity
            not in set(product((5, 20), WINDOWS, ("shallow_tree", "momentum20")))
            or row["end"] != WINDOWS[row["window"]]
            or row["status"] != "completed"
            or row["requested_dates"] != 40
        ):
            raise ValueError("TREE_PUBLIC_MODEL_IDENTITY_CHANGED")
        seen.add(identity)
        for name in ("valid_ic_dates", "valid_mse_dates"):
            count(row[name], 40)
        for metric, coverage in (
            ("mean_daily_ic", "valid_ic_dates"),
            ("mean_daily_mse", "valid_mse_dates"),
        ):
            number = row[metric]
            if number is None:
                if row[coverage] != 0:
                    raise ValueError("TREE_PUBLIC_MODEL_COVERAGE_CHANGED")
            else:
                finite(number)
                if (
                    row[coverage] == 0
                    or (metric == "mean_daily_ic" and abs(number) > 1)
                    or (metric == "mean_daily_mse" and number < 0)
                ):
                    raise ValueError("TREE_PUBLIC_MODEL_METRIC_CHANGED")
    expected = set(
        product(
            (5, 20),
            WINDOWS,
            ("ridge", "elastic_net", "shallow_tree"),
            ("equal_weight", "reversal", "momentum20"),
            (0, 20),
            (0, 20, 40),
            (0, 1),
        )
    )
    if not isinstance(value["comparisons"], list) or len(value["comparisons"]) != 432:
        raise ValueError("TREE_PUBLIC_COMPARISON_GRID_CHANGED")
    seen, accounts = set(), {}
    for row in value["comparisons"]:
        keys(
            row,
            "horizon window end arm reference buffer reference_buffer fee_bps delay arm_status reference_status arm_reason reference_reason arm_net_return reference_net_return difference reason",
        )
        identity = tuple(
            row[k]
            for k in (
                "horizon",
                "window",
                "arm",
                "reference",
                "buffer",
                "fee_bps",
                "delay",
            )
        )
        for name in ("horizon", "buffer", "reference_buffer", "fee_bps", "delay"):
            count(row[name], 40)
        if (
            identity in seen
            or identity not in expected
            or row["end"] != WINDOWS[row["window"]]
            or row["reference_buffer"]
            != (0 if row["reference"] == "equal_weight" else row["buffer"])
        ):
            raise ValueError("TREE_PUBLIC_COMPARISON_IDENTITY_CHANGED")
        seen.add(identity)
        for side, arm, buffer in (
            ("arm", row["arm"], row["buffer"]),
            ("reference", row["reference"], row["reference_buffer"]),
        ):
            status, reason, number = (
                row[side + suffix] for suffix in ("_status", "_reason", "_net_return")
            )
            if status == "completed":
                finite(number)
                if reason is not None or number <= -1:
                    raise ValueError("TREE_PUBLIC_COMPLETED_ACCOUNT_CHANGED")
            elif status != "blocked" or reason not in REASONS or number is not None:
                raise ValueError("TREE_PUBLIC_BLOCKED_ACCOUNT_CHANGED")
            key = (
                row["horizon"],
                row["window"],
                arm,
                buffer,
                row["fee_bps"],
                row["delay"],
            )
            record = status, reason, number
            if accounts.setdefault(key, record) != record:
                raise ValueError("TREE_PUBLIC_MATCHED_ACCOUNT_CHANGED")
        comparable = row["arm_status"] == row["reference_status"] == "completed"
        if comparable:
            finite(row["difference"])
            if row["reason"] is not None or not math.isclose(
                row["difference"],
                row["arm_net_return"] - row["reference_net_return"],
                abs_tol=1e-12,
                rel_tol=1e-12,
            ):
                raise ValueError("TREE_PUBLIC_RETURN_RELATION_CHANGED")
        elif row["difference"] is not None or row["reason"] != "unavailable_account":
            raise ValueError("TREE_PUBLIC_UNAVAILABLE_CHANGED")
    if seen != expected:
        raise ValueError("TREE_PUBLIC_COMPARISON_GRID_CHANGED")
    new = [
        record
        for key, record in accounts.items()
        if key[2] in ("shallow_tree", "momentum20")
    ]
    if (
        len(accounts) != 264
        or len(new) != 96
        or sum(r[0] == "completed" for r in new) != 60
        or sum(r[1] == "INVALID_RANKING_POOL" for r in new) != 18
        or sum(r[1] == "KNOWN_ACTION_BOUNDARY" for r in new) != 18
    ):
        raise ValueError("TREE_PUBLIC_ACCOUNT_COUNTS_CHANGED")
    return value


def parse_reviewed(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("TREE_PUBLIC_DUPLICATE_FIELD")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("TREE_PUBLIC_NONFINITE_JSON")

    value = validate(json.loads(raw, object_pairs_hook=pairs, parse_constant=reject))
    if canonical_hash(value) != REVIEWED_SHA256:
        raise ValueError("TREE_PUBLIC_REVIEWED_HASH_CHANGED")
    return value
