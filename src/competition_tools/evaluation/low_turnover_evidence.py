"""Read-only independent verification of exported multi-session experiments."""

import math
from datetime import date, datetime
from functools import lru_cache
from itertools import product

from ..datasets.daily_storage import safe_path
from .comparison_evidence import read_json, _csv
from .comparison_reference import rank_ic
from .holding_reference import verify_holding_account, verify_plans
from .research_diagnostics import match

VARIANTS = (
    ("equal_weight", 0),
    *((a, b) for a in ("reversal", "ridge", "elastic_net") for b in (0, 20)),
)


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_HOLDING_DATE")


def _name(row):
    return f"h{row['horizon']}-{row['window']}-{row['arm']}-b{row['buffer']}-f{row['fee_bps']}-d{row['delay']}"


def load_observations(folder):
    result = {}
    for row in _csv(
        folder / "observations.csv",
        ["date", "candidate_id", "ticker", "open", "close", "valid", "action_boundary"],
    ):
        _day(row["date"])
        key = row["date"], row["candidate_id"]
        if key in result or not key[1] or row["valid"] not in ("True", "False"):
            raise ValueError("INVALID_HOLDING_OBSERVATION")
        prices = {k: float(row[k]) if row[k] else None for k in ("open", "close")}
        if any(v is not None and not math.isfinite(v) for v in prices.values()):
            raise ValueError("NONFINITE_HOLDING_OBSERVATION")
        valid = row["valid"] == "True"
        if valid and any(v is None or v <= 0 for v in prices.values()):
            raise ValueError("INVALID_VALID_HOLDING_PRICE")
        if row["action_boundary"] not in ("True", "False"):
            raise ValueError("INVALID_ACTION_BOUNDARY_FLAG")
        result[key] = prices | dict(
            valid=valid,
            ticker=row["ticker"],
            action_boundary=row["action_boundary"] == "True",
        )
    return result


def verify_holding_export(folder):
    folder = safe_path(folder)
    report = read_json(folder / "report.json")
    if (
        report.get("schema") != "equity.low_turnover_ml.v1"
        or report.get("status") != "completed"
        or report.get("retrospective") is not True
        or report.get("formal_performance_ready") is not False
        or report.get("currency") != "USD"
    ):
        raise ValueError("INVALID_HOLDING_REPORT")
    calendar = report["calendar"]
    if (
        not isinstance(calendar, list)
        or len(calendar) < 227
        or calendar != sorted(set(calendar))
    ):
        raise ValueError("INVALID_HOLDING_CALENDAR")
    for day in calendar:
        _day(day)
    if len(report.get("accounts", [])) != 168 or len(report.get("models", [])) != 8:
        raise ValueError("INVALID_HOLDING_GRID")
    dates = calendar[:-21][-80:]
    folds = [dates[:40], dates[40:]]
    windows = {days[0]: days for days in folds}
    expected = set(product((5, 20), windows, VARIANTS, (0, 20, 40), (0, 1)))
    identities = []
    for row in report["accounts"]:
        identity = (
            row["horizon"],
            row["window"],
            (row["arm"], row["buffer"]),
            row["fee_bps"],
            row["delay"],
        )
        if (
            identity not in expected
            or identity in identities
            or row["end"] != windows[row["window"]][-1]
        ):
            raise ValueError("CHANGED_HOLDING_GRID")
        identities.append(identity)
    model_ids = {
        (h, w, m) for h in (5, 20) for w in windows for m in ("ridge", "elastic_net")
    }
    if {(r["horizon"], r["window"], r["model"]) for r in report["models"]} != model_ids:
        raise ValueError("CHANGED_HOLDING_MODEL_GRID")
    times = {}
    for row in _csv(folder / "calendar.csv", ["date", "open", "close"]):
        _day(row["date"])
        opening, closing = (
            datetime.fromisoformat(row["open"]),
            datetime.fromisoformat(row["close"]),
        )
        if (
            row["date"] in times
            or not opening.tzinfo
            or not closing.tzinfo
            or opening >= closing
        ):
            raise ValueError("INVALID_HOLDING_TIMESTAMPS")
        times[row["date"]] = closing
    if list(times) != calendar:
        raise ValueError("HOLDING_CALENDAR_EXPORT_CHANGED")
    observations = load_observations(folder)
    pool = {}
    for row in _csv(
        folder / "decisions.csv",
        ["date", "candidate_id", "session_return", "price_valid"],
    ):
        day, name = row["date"], row["candidate_id"]
        if (
            day not in times
            or row["price_valid"] not in ("True", "False")
            or name in pool.get(day, {})
        ):
            raise ValueError("INVALID_HOLDING_POOL")
        valid = row["price_valid"] == "True"
        observation = observations.get((day, name))
        if observation is None or observation["valid"] != valid:
            raise ValueError("CHANGED_HOLDING_POOL_VALIDITY")
        value = float(row["session_return"]) if row["session_return"] else None
        if valid:
            match(value, observation["close"] / observation["open"] - 1)
        pool.setdefault(day, {})[name] = dict(valid=valid, session_return=value)
        if len(pool[day]) > 500:
            raise ValueError("HOLDING_POOL_LIMIT")
    indices = {d: i for i, d in enumerate(calendar)}

    @lru_cache(maxsize=None)
    def target(horizon, day, name):
        index = indices[day]
        future = [
            observations.get((d, name))
            for d in calendar[index + 1 : index + horizon + 1]
        ]
        if len(future) != horizon or any(
            r is None or not r["valid"] or r["action_boundary"] for r in future
        ):
            return None
        return future[-1]["close"] / future[0]["open"] - 1

    models, predictions = [], {}
    for row in report["models"]:
        horizon, window, model = row["horizon"], row["window"], row["model"]
        fold = windows[window]
        preceding = calendar[: indices[window]]
        validation = preceding[-math.ceil(len(preceding) * 0.2) :]
        outer, inner = [], []
        for d in preceding:
            label_index = indices[d] + horizon
            if (
                label_index >= len(calendar)
                or times[calendar[label_index]] >= times[window]
            ):
                continue
            for name in pool.get(d, {}):
                if target(horizon, d, name) is not None:
                    outer.append(times[calendar[label_index]])
                    if (
                        d < validation[0]
                        and times[calendar[label_index]] < times[validation[0]]
                    ):
                        inner.append(times[calendar[label_index]])
        if (
            row["training_rows"] != len(outer)
            or row["inner_training_rows"] != len(inner)
            or datetime.fromisoformat(row["decision_at"]) != times[window]
            or datetime.fromisoformat(row["inner_decision_at"]) != times[validation[0]]
            or datetime.fromisoformat(row["training_latest_label_end"]) != max(outer)
            or datetime.fromisoformat(row["inner_latest_label_end"]) != max(inner)
        ):
            raise ValueError("HOLDING_PURGE_OR_CHRONOLOGY_CHANGED")
        scores, metrics = None, None
        if row["status"] == "completed":
            expected_scores = {(d, n) for d in fold for n in pool.get(d, {})}
            scores = {}
            for value in _csv(
                folder / f"h{horizon}-{window}-{model}-predictions.csv",
                ["date", "candidate_id", "prediction"],
            ):
                key = value["date"], value["candidate_id"]
                score = float(value["prediction"])
                if (
                    key in scores
                    or key not in expected_scores
                    or not math.isfinite(score)
                ):
                    raise ValueError("INVALID_HOLDING_PREDICTION")
                scores[key] = score
            if set(scores) != expected_scores or row["prediction_rows"] != len(scores):
                raise ValueError("FUTURE_FILTERED_HOLDING_PREDICTIONS")
            daily, ics, mses = [], [], []
            for d in fold:
                pairs = [
                    (scores[(d, n)], target(horizon, d, n)) for n in pool.get(d, {})
                ]
                pairs = [(score, label) for score, label in pairs if label is not None]
                mse = (
                    math.fsum((score - label) ** 2 for score, label in pairs)
                    / len(pairs)
                    if pairs
                    else None
                )
                ic = rank_ic([p[0] for p in pairs], [p[1] for p in pairs])
                daily.append(dict(date=d, count=len(pairs), mse=mse, rank_ic=ic))
                if ic is not None:
                    ics.append(ic)
                if mse is not None:
                    mses.append(mse)
            metrics = dict(
                requested_dates=40,
                valid_ic_dates=len(ics),
                valid_mse_dates=len(mses),
                mean_daily_ic=math.fsum(ics) / len(ics) if ics else None,
                mean_daily_mse=math.fsum(mses) / len(mses) if mses else None,
            )
            for key, expected_value in metrics.items():
                if expected_value is None:
                    if row["metrics"][key] is not None:
                        raise ValueError("CHANGED_MISSING_HOLDING_SCORE")
                else:
                    match(row["metrics"][key], expected_value)
            for actual_day, expected_day in zip(
                row["metrics"]["daily"], daily, strict=True
            ):
                for key, value in expected_day.items():
                    if key == "date" or value is None:
                        if actual_day[key] != value:
                            raise ValueError("CHANGED_HOLDING_DAILY_METRICS")
                    else:
                        match(actual_day[key], value)
        elif (
            row["status"] not in ("unavailable", "failed")
            or row["metrics"] is not None
            or row["prediction_rows"]
        ):
            raise ValueError("INVALID_HOLDING_MODEL_STATUS")
        predictions[(horizon, window, model)] = scores
        models.append(
            {
                key: row[key]
                for key in (
                    "horizon",
                    "window",
                    "end",
                    "model",
                    "status",
                    "params",
                    "prediction_rows",
                    "training_rows",
                    "inner_training_rows",
                )
            }
            | dict(metrics=metrics)
        )
    accounts, checked_plans = [], {}
    for row in report["accounts"]:
        h, w, arm, buffer, fee, delay = (
            row["horizon"],
            row["window"],
            row["arm"],
            row["buffer"],
            row["fee_bps"],
            row["delay"],
        )
        key = h, w, arm, buffer
        if key not in checked_plans:
            plans = read_json(folder / f"h{h}-{w}-{arm}-b{buffer}-plans.json")
            verify_plans(
                plans, pool, predictions.get((h, w, arm)), windows[w], h, arm, buffer
            )
            checked_plans[key] = plans
        artifact = read_json(folder / (_name(row) + ".json"))
        net = verify_holding_account(
            artifact["net"],
            observations,
            calendar,
            windows[w],
            checked_plans[key],
            horizon=h,
            fee_bps=fee,
            delay=delay,
        )
        gross = verify_holding_account(
            artifact["gross"],
            observations,
            calendar,
            windows[w],
            checked_plans[key],
            horizon=h,
            fee_bps=0,
            delay=delay,
        )
        for field in (
            "status",
            "reason",
            "blocked_date",
            "requested_dates",
            "valid_dates",
        ):
            if row[field] != artifact["net"][field]:
                raise ValueError("HOLDING_REPORT_COVERAGE_CHANGED")
        metrics = None
        if net is not None:
            metrics = net | dict(
                gross_return=gross["net_return"],
                cost_drag=gross["net_return"] - net["net_return"],
            )
            for field, value in metrics.items():
                match(row["metrics"][field], value)
        elif row["metrics"] is not None:
            raise ValueError("BLOCKED_HOLDING_REPORT_HAS_METRICS")
        accounts.append(
            {
                k: row[k]
                for k in (
                    "horizon",
                    "window",
                    "end",
                    "arm",
                    "buffer",
                    "fee_bps",
                    "delay",
                    "status",
                    "reason",
                    "blocked_date",
                    "requested_dates",
                    "valid_dates",
                )
            }
            | dict(metrics=metrics)
        )
    attempts = []
    for h in (5, 20):
        path = safe_path(folder / f"attempts-{h}.jsonl")
        if path.stat().st_size > 256 * 1024:
            raise ValueError("HOLDING_ATTEMPT_LOG_TOO_LARGE")
        lines = path.read_text(encoding="utf-8").splitlines()
        if not 24 <= len(lines) <= 28:
            raise ValueError("HOLDING_ATTEMPT_LIMIT_CHANGED")
        attempts.extend(lines)
    if report["fit_attempts"] != len(attempts) or not 48 <= len(attempts) <= 56:
        raise ValueError("HOLDING_FIT_LIMIT_CHANGED")
    return dict(
        currency="USD", fit_attempts=len(attempts), models=models, accounts=accounts
    )
