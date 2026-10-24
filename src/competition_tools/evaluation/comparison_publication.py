"""Aggregate-only reviewed comparison contract, with no locale-dependent facts."""

import math
import json
import re
from datetime import date, datetime, timedelta
from itertools import product

from .comparison_reference import EQUITY_ARMS, CRYPTO_ARMS, METRICS, close
from .study_identity import canonical_hash

REVIEWED_SHA256 = "e808a27d1a7bfb6a40bc7f33541849dea72047ef0fdbb692dfab1dd98abe62ac"
REASONS = {
    "EMPTY_DECISION_POOL",
    "MODEL_UNAVAILABLE",
    "INVALID_SCORES",
    "CONSTANT_SCORES",
    "INSUFFICIENT_DECISION_POOL",
    "MISSING_EXECUTION_SESSION",
    "MISSING_SELECTED_OUTCOME",
}


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("INVALID_COMPARISON_FIELDS")


def parse_public_comparison(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 2 * 1024**2:
        raise ValueError("INVALID_COMPARISON_TEXT")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("DUPLICATE_COMPARISON_FIELD")
            value[key] = item
        return value

    value = json.loads(text, object_pairs_hook=unique)
    json.dumps(value, allow_nan=False)
    return validate_public_comparison(value)


def _integer(value, maximum=1_000_000_000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("INVALID_COMPARISON_COUNT")


def _date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_COMPARISON_DATE")


def _metrics(value):
    if not isinstance(value, dict) or set(value) != set(METRICS):
        raise ValueError("INVALID_COMPARISON_METRICS")
    for name, number in value.items():
        if name == "top_asset_positive_price_pnl_share" and number is None:
            continue
        if type(number) not in (float, int) or not math.isfinite(number):
            raise ValueError("INVALID_COMPARISON_NUMBER")
    if (
        not -1 < value["net_return"]
        or not -1 < value["gross_return"]
        or not 0 <= value["max_drawdown"] <= 1
        or value["total_costs"] < 0
        or value["turnover"] < 0
        or value["cost_drag"] < -1e-10
        or value["without_best_five_days_return"] <= -1
        or (
            value["top_asset_positive_price_pnl_share"] is not None
            and not 0 <= value["top_asset_positive_price_pnl_share"] <= 1
        )
    ):
        raise ValueError("INVALID_COMPARISON_RANGE")
    close(value["cost_drag"], value["gross_return"] - value["net_return"])


def validate_cells(market, rows, windows):
    if (
        market not in ("equity", "crypto")
        or not isinstance(rows, list)
        or not isinstance(windows, dict)
    ):
        raise ValueError("INVALID_COMPARISON_GRID")
    arms, fees, periods = (
        (EQUITY_ARMS, (0, 20, 40), 20)
        if market == "equity"
        else (CRYPTO_ARMS, (0, 35, 50), 90)
    )
    expected = set(product(windows, arms, fees, (0, 1)))
    seen = set()
    for row in rows:
        _keys(
            row,
            "window end arm fee_bps delay status requested_dates valid_dates metrics reasons",
        )
        _date(row["window"])
        _date(row["end"])
        _integer(row["fee_bps"], 100)
        _integer(row["delay"], 1)
        _integer(row["requested_dates"], periods)
        _integer(row["valid_dates"], periods)
        identity = row["window"], row["arm"], row["fee_bps"], row["delay"]
        if (
            identity not in expected
            or identity in seen
            or row["end"] != windows[row["window"]]
            or row["requested_dates"] != periods
        ):
            raise ValueError("CHANGED_COMPARISON_GRID")
        seen.add(identity)
        if (
            not isinstance(row["reasons"], list)
            or any(
                not isinstance(reason, str) or reason not in REASONS
                for reason in row["reasons"]
            )
            or row["reasons"] != sorted(set(row["reasons"]))
        ):
            raise ValueError("INVALID_COMPARISON_REASONS")
        if row["status"] == "completed":
            if row["valid_dates"] != periods or row["reasons"]:
                raise ValueError("INCOMPLETE_COMPARISON_METRICS")
            _metrics(row["metrics"])
        elif (
            row["status"] != "blocked"
            or row["metrics"] is not None
            or not row["reasons"]
            or row["valid_dates"] >= periods
        ):
            raise ValueError("INVALID_COMPARISON_STATUS")
    if seen != expected:
        raise ValueError("INCOMPLETE_COMPARISON_GRID")
    return rows


def _quality(value):
    _keys(value, "daily minute conversion")
    daily, minute, conversion = value["daily"], value["minute"], value["conversion"]
    _keys(
        daily,
        "rows source_codes candidate_identities observed_sessions first_date last_date duplicate_candidate_sessions non_session_rows invalid_ohlc_rows nonfinite_numeric_values missing_numeric_values negative_dollar_volume_rows unresolved_identity_rows formal_common_stock_ready availability_verified corporate_action_coverage",
    )
    for key, item in daily.items():
        if key in ("first_date", "last_date"):
            _date(item)
        elif key not in (
            "formal_common_stock_ready",
            "availability_verified",
            "corporate_action_coverage",
        ):
            _integer(item)
    if (
        daily["formal_common_stock_ready"] is not False
        or daily["availability_verified"] is not False
        or daily["corporate_action_coverage"] != "incomplete"
    ):
        raise ValueError("UNSUPPORTED_FORMAL_ACCEPTANCE")
    _keys(
        minute,
        "rows source_codes duplicate_minute_keys regular_rows regular_rows_outside_session zero_volume_rows invalid_volume_rows invalid_traded_ohlc_rows nonfinite_numeric_values missing_quote_rows crossed_quote_rows wide_quote_rows scope full_conversion_certified",
    )
    for key, item in minute.items():
        if key not in ("scope", "full_conversion_certified"):
            _integer(item, 150000)
    if (
        minute["scope"] != "one_bounded_row_group"
        or minute["full_conversion_certified"] is not False
    ):
        raise ValueError("UNSUPPORTED_CONVERSION_CERTIFICATION")
    _keys(conversion, "status days rows parquet_bytes independently_verified")
    for key in ("days", "rows", "parquet_bytes"):
        _integer(conversion[key], 1_000_000_000_000)
    if (
        conversion["status"] != "complete"
        or conversion["independently_verified"] is not False
    ):
        raise ValueError("INVALID_CONVERSION_EVIDENCE")


def validate_public_comparison(value):
    _keys(
        value,
        "schema retrospective formal_performance_ready scientific equity crypto data_quality future",
    )
    if (
        value["schema"] != "competition.strategy_comparison_public.v1"
        or value["retrospective"] is not True
        or value["formal_performance_ready"] is not False
    ):
        raise ValueError("INVALID_COMPARISON_SCOPE")
    _keys(
        value["scientific"],
        "commit plan_sha256 result_sha256 equity_input_sha256 crypto_input_sha256",
    )
    for key, identifier in value["scientific"].items():
        if not isinstance(identifier, str) or not re.fullmatch(
            "[0-9a-f]{40}" if key == "commit" else "[0-9a-f]{64}", identifier
        ):
            raise ValueError("INVALID_COMPARISON_SCIENCE_IDENTITY")
    eq, crypto = value["equity"], value["crypto"]
    _keys(eq, "currency accounting_model fit_attempts folds accounts")
    _keys(crypto, "currency accounting_model products accounts")
    if (
        eq["currency"] != "USD"
        or eq["accounting_model"] != "intraday_cash_proxy.v1"
        or crypto["currency"] != "USDT"
        or crypto["accounting_model"] != "self_financing_daily.v1"
        or type(crypto["products"]) is not int
        or crypto["products"] != 8
    ):
        raise ValueError("CHANGED_COMPARISON_MODEL")
    _integer(eq["fit_attempts"], 42)
    if (
        eq["fit_attempts"] < 36
        or not isinstance(eq["folds"], list)
        or len(eq["folds"]) != 3
    ):
        raise ValueError("CHANGED_COMPARISON_FITS")
    windows = {}
    for fold in eq["folds"]:
        _keys(fold, "start end models")
        _date(fold["start"])
        _date(fold["end"])
        if (
            fold["start"] in windows
            or not isinstance(fold["models"], list)
            or len(fold["models"]) != 2
        ):
            raise ValueError("INVALID_COMPARISON_FOLD")
        windows[fold["start"]] = fold["end"]
        if {m.get("model") for m in fold["models"]} != {"ridge", "elastic_net"}:
            raise ValueError("CHANGED_COMPARISON_MODELS")
        for model in fold["models"]:
            _keys(
                model,
                "model status params valid_ic_dates mean_daily_ic mean_daily_mse scored_rows",
            )
            _integer(model["valid_ic_dates"], 20)
            _integer(model["scored_rows"], 10000)
            if model["status"] not in (
                "completed",
                "unavailable",
                "failed",
            ) or not isinstance(model["params"], dict):
                raise ValueError("INVALID_COMPARISON_MODEL_STATUS")
            for key in ("mean_daily_ic", "mean_daily_mse"):
                number = model[key]
                if number is not None and (
                    type(number) not in (float, int) or not math.isfinite(number)
                ):
                    raise ValueError("INVALID_COMPARISON_MODEL_METRIC")
            if (model["valid_ic_dates"] == 0) != (model["mean_daily_ic"] is None):
                raise ValueError("CHANGED_COMPARISON_IC_COVERAGE")
    validate_cells("equity", eq["accounts"], windows)
    crypto_windows = {r["window"]: r["end"] for r in crypto["accounts"]}
    if len(crypto_windows) != 12 or any(
        date.fromisoformat(end) - date.fromisoformat(start) != timedelta(days=89)
        for start, end in crypto_windows.items()
    ):
        raise ValueError("CHANGED_CRYPTO_COMPARISON_WINDOWS")
    validate_cells("crypto", crypto["accounts"], crypto_windows)
    _quality(value["data_quality"])
    future = value["future"]
    _keys(
        future,
        "status active frozen_at known_cutoff_at first_eligible_observation_at unseen_data_certified",
    )
    if (
        future["status"] != "awaiting_fresh_verified_data"
        or future["active"] is not False
        or future["first_eligible_observation_at"] is not None
        or future["unseen_data_certified"] is not False
    ):
        raise ValueError("UNSUPPORTED_PROSPECTIVE_ACCEPTANCE")
    for key in ("frozen_at", "known_cutoff_at"):
        stamp = datetime.fromisoformat(future[key])
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            raise ValueError("INVALID_COMPARISON_FREEZE_TIME")
    if canonical_hash(value) != REVIEWED_SHA256:
        raise ValueError("UNREVIEWED_COMPARISON_ARTIFACT")
    return value
