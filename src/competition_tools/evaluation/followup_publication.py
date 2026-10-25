"""Closed reviewed facts for a separate validation study and recovery record."""

import json
import re
from datetime import date, datetime, timedelta
from itertools import product
from statistics import median

from .low_turnover_publication import keys, count, finite, day, _holding
from .study_identity import canonical_hash
from .research_diagnostics import match

REVIEWED_SHA256 = "71467bfd20adc433b4fd8d767b8cfc730b045b757e94114cb39de6dfb43d4d1f"


def validate_candidate(value):
    keys(
        value,
        "schema retrospective formal_performance_ready scientific validation_sessions equity crypto security observation",
    )
    if (
        value["schema"] != "competition.evidence_followup_public.v1"
        or value["retrospective"] is not True
        or value["formal_performance_ready"] is not False
        or type(value["validation_sessions"]) is not int
        or value["validation_sessions"] != 60
    ):
        raise ValueError("INVALID_FOLLOWUP_PROTOCOL")
    keys(value["scientific"], "commit plan_sha256 result_sha256 input_sha256")
    for name, digest in value["scientific"].items():
        if not isinstance(digest, str) or not re.fullmatch(
            "[a-f0-9]{40}" if name == "commit" else "[a-f0-9]{64}", digest
        ):
            raise ValueError("INVALID_FOLLOWUP_IDENTITY")
    _holding(value["equity"])
    crypto = value["crypto"]
    keys(
        crypto,
        "schema currency requested comparable return_wins median_return_difference same_volatility_claimed causal_alpha_claimed rows",
    )
    if (
        crypto["schema"] != "competition.crypto_paired_controls.v1"
        or crypto["currency"] != "USDT"
        or crypto["same_volatility_claimed"] is not False
        or crypto["causal_alpha_claimed"] is not False
    ):
        raise ValueError("INVALID_FOLLOWUP_CRYPTO")
    seen, windows, completed = set(), {}, []
    for row in crypto["rows"]:
        keys(
            row,
            "window end fee_bps delay status return_difference exposure_difference drawdown_difference turnover_difference",
        )
        day(row["window"])
        day(row["end"])
        count(row["fee_bps"], 50)
        count(row["delay"], 1)
        identity = row["window"], row["fee_bps"], row["delay"]
        if (
            identity in seen
            or row["fee_bps"] not in (0, 35, 50)
            or (date.fromisoformat(row["end"]) - date.fromisoformat(row["window"])).days
            != 89
        ):
            raise ValueError("INVALID_PAIR_GRID")
        seen.add(identity)
        if windows.setdefault(row["window"], row["end"]) != row["end"]:
            raise ValueError("CHANGED_PAIR_WINDOW")
        for name in ("return", "exposure", "drawdown", "turnover"):
            number = row[name + "_difference"]
            if row["status"] == "completed":
                finite(number)
            elif row["status"] != "blocked" or number is not None:
                raise ValueError("INVALID_PAIR_STATUS")
        if row["status"] == "completed":
            completed.append(row)
    if len(windows) != 12 or seen != set(product(windows, (0, 35, 50), (0, 1))):
        raise ValueError("INCOMPLETE_PAIR_GRID")
    for name in ("requested", "comparable", "return_wins"):
        count(crypto[name], 72)
    if (
        crypto["requested"] != len(seen)
        or crypto["comparable"] != len(completed)
        or crypto["return_wins"] != sum(r["return_difference"] > 0 for r in completed)
    ):
        raise ValueError("CHANGED_PAIR_SUMMARY")
    match(
        crypto["median_return_difference"],
        median(r["return_difference"] for r in completed),
    )
    security = value["security"]
    keys(security, "requested accepted retained_contracts complete_history_verified")
    for name in ("requested", "accepted", "retained_contracts"):
        count(security[name], 10)
    if security != dict(
        requested=10, accepted=0, retained_contracts=10, complete_history_verified=False
    ):
        raise ValueError("UNVERIFIED_POOL_PROMOTION")
    obs = value["observation"]
    keys(
        obs,
        "status registry_frozen warmup_end freeze_at next_eligible_date accepted_observations availability_review_required previous_attempts previous_spend_uncertain new_attempts new_bytes reused_responses new_spend_uncertain execution_authorized",
    )
    for name, limit in (
        ("accepted_observations", 0),
        ("previous_attempts", 345),
        ("new_attempts", 64),
        ("new_bytes", 4 * 1024**2),
        ("reused_responses", 384),
    ):
        count(obs[name], limit)
    day(obs["warmup_end"])
    day(obs["next_eligible_date"])
    frozen = datetime.fromisoformat(obs["freeze_at"])
    if (
        obs["status"] != "awaiting_new_bar"
        or obs["registry_frozen"] is not True
        or obs["availability_review_required"] is not True
        or obs["execution_authorized"] is not False
        or obs["previous_attempts"] != 345
        or obs["previous_spend_uncertain"] is not True
        or obs["new_spend_uncertain"] is not False
        or frozen.tzinfo is None
        or date.fromisoformat(obs["next_eligible_date"])
        != date.fromisoformat(obs["warmup_end"]) + timedelta(days=1)
        or frozen.date().isoformat() != obs["next_eligible_date"]
        or obs["reused_responses"] + obs["new_attempts"] != 384
    ):
        raise ValueError("INVALID_FOLLOWUP_OBSERVATION")
    return value


def summary(value):
    validate_candidate(value)
    return dict(
        scientific=value["scientific"],
        validation_sessions=60,
        completed=sum(r["status"] == "completed" for r in value["equity"]["accounts"]),
        blocked=sum(r["status"] == "blocked" for r in value["equity"]["accounts"]),
        fit_attempts=value["equity"]["fit_attempts"],
        accepted_stocks=value["security"]["accepted"],
        requested_stocks=value["security"]["requested"],
        paired=value["crypto"]["comparable"],
        wins=value["crypto"]["return_wins"],
        median_pair_difference=value["crypto"]["median_return_difference"],
        **{
            k: value["observation"][k]
            for k in (
                "warmup_end",
                "freeze_at",
                "next_eligible_date",
                "accepted_observations",
                "new_attempts",
                "new_bytes",
                "reused_responses",
            )
        },
    )


def parse_reviewed(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 1024**2:
        raise ValueError("FOLLOWUP_TEXT_LIMIT")

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("DUPLICATE_FOLLOWUP_FIELD")
            result[key] = item
        return result

    value = json.loads(text, object_pairs_hook=unique)
    json.dumps(value, allow_nan=False)
    validate_candidate(value)
    if canonical_hash(value) != REVIEWED_SHA256:
        raise ValueError("UNREVIEWED_FOLLOWUP_FACTS")
    return value
