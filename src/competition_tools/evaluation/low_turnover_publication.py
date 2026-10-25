"""Closed aggregate contract for reviewed low-turnover research evidence."""

import json
import math
import re
from datetime import date, datetime, timedelta
from itertools import product

from .study_identity import canonical_hash
from .research_diagnostics import match

REVIEWED_SHA256 = "fa7e00c9b9582caf7c6656e5151520cde588304dc523b28953e9eeaf22d2a6e2"
VARIANTS = (
    ("equal_weight", 0),
    *((a, b) for a in ("reversal", "ridge", "elastic_net") for b in (0, 20)),
)
REASONS = {
    "EMPTY_DECISION_POOL",
    "MODEL_UNAVAILABLE",
    "INVALID_RANKING_POOL",
    "CONSTANT_SCORES",
    "MISSING_HELD_OR_SELECTED_PRICE",
    "KNOWN_ACTION_BOUNDARY",
}
CRYPTO_ARMS = (
    "buy_hold_equal_weight",
    "fixed60_weekly",
    "trend_weekly",
    "matched_weekly",
)


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("INVALID_LOW_TURNOVER_FIELDS")


def count(value, maximum=1_000_000_000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("INVALID_LOW_TURNOVER_COUNT")


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("INVALID_LOW_TURNOVER_NUMBER")


def day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_LOW_TURNOVER_DATE")


def _holding(value):
    keys(value, "currency fit_attempts models accounts")
    count(value["fit_attempts"], 56)
    if (
        value["currency"] != "USD"
        or value["fit_attempts"] < 48
        or len(value["accounts"]) != 168
        or len(value["models"]) != 8
    ):
        raise ValueError("INVALID_LOW_TURNOVER_GRID")
    windows, seen = {}, set()
    for row in value["accounts"]:
        keys(
            row,
            "horizon window end arm buffer fee_bps delay status reason blocked_date requested_dates valid_dates metrics",
        )
        day(row["window"])
        day(row["end"])
        for name in (
            "horizon",
            "buffer",
            "fee_bps",
            "delay",
            "requested_dates",
            "valid_dates",
        ):
            count(row[name], 100)
        identity = (
            row["horizon"],
            row["window"],
            (row["arm"], row["buffer"]),
            row["fee_bps"],
            row["delay"],
        )
        if (
            row["horizon"] not in (5, 20)
            or (row["arm"], row["buffer"]) not in VARIANTS
            or row["fee_bps"] not in (0, 20, 40)
            or row["delay"] not in (0, 1)
            or identity in seen
            or row["end"] <= row["window"]
            or row["requested_dates"] != 41
        ):
            raise ValueError("CHANGED_LOW_TURNOVER_GRID")
        if windows.setdefault(row["window"], row["end"]) != row["end"]:
            raise ValueError("CHANGED_LOW_TURNOVER_WINDOW")
        seen.add(identity)
        if row["status"] == "completed":
            if (
                row["reason"] is not None
                or row["blocked_date"] is not None
                or row["valid_dates"] != 41
            ):
                raise ValueError("INCOMPLETE_LOW_TURNOVER_RESULT")
            metrics = row["metrics"]
            keys(
                metrics,
                "net_return max_drawdown total_costs turnover gross_return cost_drag",
            )
            for number in metrics.values():
                finite(number)
            if (
                min(metrics["net_return"], metrics["gross_return"]) <= -1
                or not 0 <= metrics["max_drawdown"] <= 1
                or min(metrics["total_costs"], metrics["turnover"]) < 0
                or metrics["cost_drag"] < -1e-10
            ):
                raise ValueError("INVALID_LOW_TURNOVER_METRICS")
            match(metrics["cost_drag"], metrics["gross_return"] - metrics["net_return"])
            if row["fee_bps"] == 0:
                match(metrics["total_costs"], 0)
                match(metrics["cost_drag"], 0)
        elif row["status"] == "blocked":
            if (
                row["metrics"] is not None
                or row["reason"] not in REASONS
                or row["valid_dates"] >= 41
            ):
                raise ValueError("INVALID_LOW_TURNOVER_BLOCK")
            day(row["blocked_date"])
        else:
            raise ValueError("UNKNOWN_LOW_TURNOVER_STATUS")
    if len(windows) != 2 or seen != set(
        product((5, 20), windows, VARIANTS, (0, 20, 40), (0, 1))
    ):
        raise ValueError("INCOMPLETE_LOW_TURNOVER_GRID")
    model_ids = set()
    for row in value["models"]:
        keys(
            row,
            "horizon window end model status params prediction_rows training_rows inner_training_rows metrics",
        )
        identity = row["horizon"], row["window"], row["model"]
        if (
            row["horizon"] not in (5, 20)
            or row["window"] not in windows
            or row["end"] != windows[row["window"]]
            or row["model"] not in ("ridge", "elastic_net")
            or identity in model_ids
        ):
            raise ValueError("CHANGED_LOW_TURNOVER_MODELS")
        model_ids.add(identity)
        for name in ("prediction_rows", "training_rows", "inner_training_rows"):
            count(row[name], 658472)
        if row["inner_training_rows"] > row["training_rows"]:
            raise ValueError("INVALID_LOW_TURNOVER_TRAINING")
        if row["status"] == "completed":
            params, metrics = row["params"], row["metrics"]
            keys(params, "alpha" if row["model"] == "ridge" else "alpha l1_ratio")
            if params["alpha"] not in (
                (0.1, 1.0, 10.0) if row["model"] == "ridge" else (0.0001, 0.001, 0.01)
            ) or (
                row["model"] == "elastic_net"
                and params["l1_ratio"] not in (0.1, 0.5, 0.9)
            ):
                raise ValueError("CHANGED_LOW_TURNOVER_SEARCH")
            keys(
                metrics,
                "requested_dates valid_ic_dates valid_mse_dates mean_daily_ic mean_daily_mse",
            )
            for name in ("requested_dates", "valid_ic_dates", "valid_mse_dates"):
                count(metrics[name], 40)
            if (
                metrics["requested_dates"] != 40
                or metrics["valid_ic_dates"] > metrics["valid_mse_dates"]
                or not 0 < row["prediction_rows"] <= 20000
            ):
                raise ValueError("INVALID_LOW_TURNOVER_MODEL_COVERAGE")
            for name in ("mean_daily_ic", "mean_daily_mse"):
                if metrics[name] is not None:
                    finite(metrics[name])
            if (
                metrics["mean_daily_ic"] is not None
                and not -1 <= metrics["mean_daily_ic"] <= 1
            ) or (
                metrics["mean_daily_mse"] is not None and metrics["mean_daily_mse"] < 0
            ):
                raise ValueError("INVALID_LOW_TURNOVER_MODEL_METRICS")
        elif (
            row["status"] not in ("failed", "unavailable")
            or row["metrics"] is not None
            or row["params"] is not None
            or row["prediction_rows"]
        ):
            raise ValueError("INVALID_LOW_TURNOVER_MODEL_STATUS")


def _costs(value):
    keys(value, "requested completed accounts")
    if value["requested"] != 24 or len(value["accounts"]) != 24:
        raise ValueError("INVALID_COST_DIAGNOSTIC_GRID")
    seen, windows, completed = set(), set(), 0
    for row in value["accounts"]:
        keys(
            row,
            "window arm delay status valid_dates requested_dates gross_return break_even_one_way_bps mean_daily_turnover",
        )
        day(row["window"])
        count(row["delay"], 1)
        count(row["valid_dates"], 20)
        if (
            row["arm"] not in ("equal_weight", "reversal", "ridge", "elastic_net")
            or row["requested_dates"] != 20
        ):
            raise ValueError("INVALID_COST_DIAGNOSTIC_SCOPE")
        identity = row["window"], row["arm"], row["delay"]
        if identity in seen:
            raise ValueError("DUPLICATE_COST_DIAGNOSTIC")
        seen.add(identity)
        windows.add(row["window"])
        if row["status"] == "completed":
            completed += 1
            finite(row["gross_return"])
            finite(row["mean_daily_turnover"])
            if (
                row["valid_dates"] != 20
                or row["gross_return"] <= -1
                or row["mean_daily_turnover"] < 0
            ):
                raise ValueError("INVALID_COST_DIAGNOSTIC_RESULT")
            threshold = row["break_even_one_way_bps"]
            if row["gross_return"] < 0:
                if threshold is not None:
                    raise ValueError("NEGATIVE_GROSS_HAS_NO_NONNEGATIVE_THRESHOLD")
            else:
                finite(threshold)
                match(
                    threshold, 10000 * math.tanh(math.log1p(row["gross_return"]) / 40)
                )
        elif (
            row["status"] != "blocked"
            or row["valid_dates"] >= 20
            or any(
                row[k] is not None
                for k in (
                    "gross_return",
                    "break_even_one_way_bps",
                    "mean_daily_turnover",
                )
            )
        ):
            raise ValueError("INVALID_BLOCKED_COST_DIAGNOSTIC")
    if len(windows) != 3 or value["completed"] != completed:
        raise ValueError("INCOMPLETE_COST_DIAGNOSTICS")


def _crypto(value):
    keys(value, "currency accounts")
    if value["currency"] != "USDT" or len(value["accounts"]) != 288:
        raise ValueError("INVALID_CRYPTO_ATTRIBUTION_GRID")
    seen, windows = set(), set()
    for row in value["accounts"]:
        keys(
            row,
            "window end arm fee_bps delay net_return components dates mean_post_trade_exposure down_market_dates down_market_strategy_pnl down_market_full_reference_pnl",
        )
        day(row["window"])
        day(row["end"])
        for key in ("fee_bps", "delay", "dates", "down_market_dates"):
            count(row[key], 100)
        if (
            row["arm"] not in CRYPTO_ARMS
            or row["fee_bps"] not in (0, 35, 50)
            or row["delay"] not in (0, 1)
            or row["dates"] != 90
            or row["down_market_dates"] > 90
            or date.fromisoformat(row["end"]) - date.fromisoformat(row["window"])
            != timedelta(days=89)
        ):
            raise ValueError("CHANGED_CRYPTO_ATTRIBUTION_GRID")
        identity = row["window"], row["arm"], row["fee_bps"], row["delay"]
        if identity in seen:
            raise ValueError("DUPLICATE_CRYPTO_ATTRIBUTION")
        seen.add(identity)
        windows.add(row["window"])
        keys(row["components"], "market exposure selection cost")
        for number in (
            *row["components"].values(),
            *(
                row[k]
                for k in (
                    "net_return",
                    "mean_post_trade_exposure",
                    "down_market_strategy_pnl",
                    "down_market_full_reference_pnl",
                )
            ),
        ):
            finite(number)
        match(math.fsum(row["components"].values()), row["net_return"])
        if (
            row["net_return"] <= -1
            or not 0 <= row["mean_post_trade_exposure"] <= 1 + 1e-10
            or row["components"]["cost"] > 0
        ):
            raise ValueError("INVALID_CRYPTO_ATTRIBUTION")
    if len(windows) != 12 or seen != set(
        product(windows, CRYPTO_ARMS, (0, 35, 50), (0, 1))
    ):
        raise ValueError("INCOMPLETE_CRYPTO_ATTRIBUTION")


def _security(value):
    numeric = "candidate_days identity_segments unresolved_identity_segments unresolved_candidate_days unmatched_interval_days missing_master_days source_seed_events source_split_seeds seed_split_boundary_matches large_raw_boundary_jumps independently_verified_type_days primary_announcements_reviewed"
    keys(
        value,
        "schema "
        + numeric
        + " source_classifications corporate_action_coverage availability_verified formal_performance_ready prices_modified",
    )
    for name in numeric.split():
        count(value[name])
    allowed = {
        "unverified_security_type",
        "warrant_evidence",
        "date_bounded_identity_candidates",
        "reorganization_old_new_equity_requires_split_identity",
    }
    if (
        not isinstance(value["source_classifications"], dict)
        or not set(value["source_classifications"]) <= allowed
    ):
        raise ValueError("INVALID_SECURITY_CLASSIFICATIONS")
    for number in value["source_classifications"].values():
        count(number)
    if (
        value["schema"] != "competition.security_evidence_audit.v1"
        or value["corporate_action_coverage"] != "incomplete"
        or any(
            value[k] is not False
            for k in (
                "availability_verified",
                "formal_performance_ready",
                "prices_modified",
            )
        )
        or value["independently_verified_type_days"] != 0
        or value["unresolved_candidate_days"] > value["candidate_days"]
        or value["primary_announcements_reviewed"] > value["source_seed_events"]
    ):
        raise ValueError("PROMOTED_SECURITY_EVIDENCE")


def _observation(value):
    keys(
        value,
        "status registry_frozen protocol_id frozen_at crypto_warmup_end us_warmup_end accepted_observations first_eligible_observation_at download issue_codes",
    )
    frozen = datetime.fromisoformat(value["frozen_at"])
    for k in ("crypto_warmup_end", "us_warmup_end"):
        day(value[k])
    if (
        not frozen.tzinfo
        or value["status"] != "awaiting_new_data"
        or type(value["registry_frozen"]) is not bool
        or type(value["accepted_observations"]) is not int
        or value["accepted_observations"] != 0
        or value["first_eligible_observation_at"] is not None
    ):
        raise ValueError("PROMOTED_PROSPECTIVE_EVIDENCE")
    if value["registry_frozen"]:
        if not isinstance(value["protocol_id"], str) or not re.fullmatch(
            "[a-f0-9]{64}", value["protocol_id"]
        ):
            raise ValueError("INVALID_OBSERVATION_IDENTITY")
    elif value["protocol_id"] is not None:
        raise ValueError("UNFROZEN_OBSERVATION_IDENTITY")
    download = value["download"]
    keys(download, "status attempts transferred_bytes")
    count(download["attempts"], 496)
    count(download["transferred_bytes"], 16 * 1024**2)
    if download["status"] not in ("not_attempted", "acquired", "failed", "blocked"):
        raise ValueError("INVALID_OBSERVATION_DOWNLOAD")
    allowed = {
        "STALE_WARMUP",
        "INCOMPLETE_WARMUP",
        "DOWNLOAD_FAILED",
        "US_STALE_WARMUP",
        "AVAILABILITY_UNREVIEWED",
        "NEW_BAR_NOT_COMPLETED",
        "ARCHIVE_UNAVAILABLE",
        "BUDGET_EXHAUSTED",
        "NO_FRESH_SOURCE",
        "UNKNOWN_AVAILABILITY",
    }
    if (
        not isinstance(value["issue_codes"], list)
        or any(k not in allowed for k in value["issue_codes"])
        or len(set(value["issue_codes"])) != len(value["issue_codes"])
    ):
        raise ValueError("INVALID_OBSERVATION_ISSUES")


def validate_candidate(value):
    keys(
        value,
        "schema retrospective formal_performance_ready scientific equity cost_diagnostics crypto security observation",
    )
    if (
        value["schema"] != "competition.low_turnover_public.v1"
        or value["retrospective"] is not True
        or value["formal_performance_ready"] is not False
    ):
        raise ValueError("INVALID_LOW_TURNOVER_SCOPE")
    keys(
        value["scientific"],
        "commit plan_sha256 result_sha256 daily_input_sha256 parent_comparison_sha256",
    )
    for key, digest in value["scientific"].items():
        if not isinstance(digest, str) or not re.fullmatch(
            "[a-f0-9]{40}" if key == "commit" else "[a-f0-9]{64}", digest
        ):
            raise ValueError("INVALID_LOW_TURNOVER_IDENTITY")
    _holding(value["equity"])
    _costs(value["cost_diagnostics"])
    _crypto(value["crypto"])
    _security(value["security"])
    _observation(value["observation"])
    return value


def parse_reviewed(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 2 * 1024**2:
        raise ValueError("LOW_TURNOVER_TEXT_LIMIT")

    def unique(pairs):
        output = {}
        for key, item in pairs:
            if key in output:
                raise ValueError("DUPLICATE_LOW_TURNOVER_FIELD")
            output[key] = item
        return output

    value = json.loads(text, object_pairs_hook=unique)
    json.dumps(value, allow_nan=False)
    validate_candidate(value)
    if canonical_hash(value) != REVIEWED_SHA256:
        raise ValueError("UNREVIEWED_LOW_TURNOVER_FACTS")
    return value
