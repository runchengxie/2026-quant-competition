"""Independent stdlib validation of the public, aggregate-only predictive receipt."""

import math
import re
from datetime import date


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("Unexpected predictive fields")


def _integer(value, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid predictive integer")


def _number(value, low, high, nullable=False):
    if value is None and nullable:
        return
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError("Invalid predictive number")


def _metrics(metrics, start, end):
    _keys(
        metrics,
        "requested_dates valid_ic_dates valid_mse_dates mean_daily_ic mean_daily_mse daily",
    )
    for key in ["requested_dates", "valid_ic_dates", "valid_mse_dates"]:
        _integer(metrics[key], 0, 20)
    if metrics["requested_dates"] != 20 or len(metrics["daily"]) != 20:
        raise ValueError("Expected fixed twenty-date test block")
    dates, ics, mses = [], [], []
    for row in metrics["daily"]:
        _keys(row, "date count mse rank_ic ic_reason")
        date.fromisoformat(row["date"])
        dates.append(row["date"])
        _integer(row["count"], 0, 500)
        _number(row["mse"], 0, 1_000_000, True)
        _number(row["rank_ic"], -1, 1, True)
        if row["rank_ic"] is not None:
            if row["count"] < 30 or row["ic_reason"] is not None:
                raise ValueError("Invalid IC coverage")
            ics.append(row["rank_ic"])
        elif row["ic_reason"] not in [
            "fewer_than_30_candidates",
            "constant_scores_or_labels",
        ]:
            raise ValueError("Missing IC reason")
        if row["mse"] is not None:
            if row["count"] == 0:
                raise ValueError("MSE without observations")
            mses.append(row["mse"])
    if dates != sorted(set(dates)) or dates[0] != start or dates[-1] != end:
        raise ValueError("Changed test calendar")
    for key, observations, coverage in [
        ("mean_daily_ic", ics, "valid_ic_dates"),
        ("mean_daily_mse", mses, "valid_mse_dates"),
    ]:
        value = metrics[key]
        _number(
            value,
            -1 if key.endswith("ic") else 0,
            1 if key.endswith("ic") else 1_000_000,
            True,
        )
        expected = sum(observations) / len(observations) if observations else None
        if (
            metrics[coverage] != len(observations)
            or (expected is None) != (value is None)
            or (
                expected is not None
                and not math.isclose(expected, value, rel_tol=1e-12, abs_tol=1e-14)
            )
        ):
            raise ValueError("Daily metrics do not reconcile")


def validate_public_predictive(data):
    _keys(
        data,
        "schema_version scope source_sha256 source_start source_end source_candidate_count unresolved_candidate_count fit_attempts formal_common_stock_ready pnl_available availability folds",
    )
    if (
        type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["scope"] != "retrospective_source_candidate_prediction"
    ):
        raise ValueError("Unsupported predictive contract")
    if (
        data["formal_common_stock_ready"] is not False
        or data["pnl_available"] is not False
        or data["availability"] != "bar_close_proxy_unverified"
    ):
        raise ValueError("Prediction cannot imply accepted trading performance")
    if not re.fullmatch("[a-f0-9]{64}", data["source_sha256"]):
        raise ValueError("Invalid source hash")
    for key in ["source_start", "source_end"]:
        date.fromisoformat(data[key])
    _integer(data["fit_attempts"], 1, 48)
    _integer(data["source_candidate_count"], 1)
    _integer(data["unresolved_candidate_count"], 0, data["source_candidate_count"])
    if len(data["folds"]) != 3:
        raise ValueError("Expected three fixed test blocks")
    previous = data["source_start"]
    for fold in data["folds"]:
        _keys(
            fold,
            "start end training_calendar_dates validation_start test_rows test_candidate_count models",
        )
        if not previous < fold["start"] <= fold["end"] < data["source_end"]:
            raise ValueError("Overlapping or out-of-range test blocks")
        previous = fold["end"]
        _integer(fold["training_calendar_dates"], 126)
        if not data["source_start"] < fold["validation_start"] < fold["start"]:
            raise ValueError("Invalid validation boundary")
        _integer(fold["test_rows"], 0, 10_000)
        _integer(fold["test_candidate_count"], 0, data["source_candidate_count"])
        if [m["model"] for m in fold["models"]] != [
            "ridge",
            "elastic_net",
            "constant_zero",
            "session_return_rank",
        ]:
            raise ValueError("Missing declared models or baselines")
        for model in fold["models"]:
            _keys(model, "model metrics")
            _metrics(model["metrics"], fold["start"], fold["end"])
            if sum(d["count"] for d in model["metrics"]["daily"]) != fold["test_rows"]:
                raise ValueError("Test row coverage mismatch")
    return data
