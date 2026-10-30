"""Independent stdlib checks of new predictions, selections and actual-unit paths."""

import math
from itertools import product

from ..project_storage import relocated_path
from .comparison_evidence import _csv
from .comparison_reference import rank_ic
from .holding_reference import verify_holding_account, verify_plans
from .low_turnover_evidence import load_observations
from .research_diagnostics import match
from .tree_study import PROTOCOL, read, verify_binding


def same(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError("TREE_OBJECT_FIELDS_CHANGED")
        for key, value in expected.items():
            same(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("TREE_LIST_CHANGED")
        for a, b in zip(actual, expected, strict=True):
            same(a, b)
    elif expected is None or isinstance(expected, (str, bool)):
        if actual != expected or type(actual) is not type(expected):
            raise ValueError("TREE_VALUE_CHANGED")
    else:
        match(actual, expected)


def name(row):
    return f"h{row['horizon']}-{row['window']}-{row['arm']}-b{row['buffer']}-f{row['fee_bps']}-d{row['delay']}"


def momentum(observations, calendar, day, candidate):
    index = calendar.index(day)
    if index < 20:
        return None
    rows = [observations.get((d, candidate)) for d in calendar[index - 20 : index + 1]]
    if (
        any(r is None or not r["valid"] or r["action_boundary"] for r in rows)
        or len({r["ticker"] for r in rows}) != 1
        or any(r["ticker"].strip() in ("", "nan", "None") for r in rows)
    ):
        return None
    return rows[-1]["close"] / rows[0]["close"] - 1


def target(observations, calendar, horizon, day, candidate):
    index = calendar.index(day)
    rows = [
        observations.get((d, candidate))
        for d in calendar[index + 1 : index + horizon + 1]
    ]
    if len(rows) != horizon or any(
        r is None or not r["valid"] or r["action_boundary"] for r in rows
    ):
        return None
    return rows[-1]["close"] / rows[0]["open"] - 1


def scores(path, expected_keys, *, missing=False):
    values = {}
    for row in _csv(path, ["date", "candidate_id", "prediction"]):
        key = row["date"], row["candidate_id"]
        value = float(row["prediction"]) if row["prediction"] else None
        if (
            key in values
            or key not in expected_keys
            or (value is None and not missing)
            or (value is not None and not math.isfinite(value))
        ):
            raise ValueError("INVALID_TREE_PREDICTION")
        values[key] = value
    if set(values) != set(expected_keys):
        raise ValueError("TREE_PREDICTION_GRID_CHANGED")
    return values


def metrics(prediction, pool, observations, calendar, horizon, dates, *, ranking=False):
    daily = []
    for day in dates:
        pairs = [
            (prediction.get((day, n)), target(observations, calendar, horizon, day, n))
            for n in pool.get(day, {})
        ]
        pairs = [(p, y) for p, y in pairs if y is not None]
        missing = any(p is None for p, y in pairs)
        mse = (
            math.fsum((p - y) ** 2 for p, y in pairs) / len(pairs)
            if pairs and not missing and not ranking
            else None
        )
        ic = (
            rank_ic([p for p, y in pairs], [y for p, y in pairs])
            if not missing
            else None
        )
        reason = (
            "missing_predictions"
            if missing
            else "fewer_than_30_candidates"
            if len(pairs) < 30
            else "constant_scores_or_labels"
            if ic is None
            else None
        )
        daily.append(
            dict(date=day, count=len(pairs), mse=mse, rank_ic=ic, ic_reason=reason)
        )
    ics = [r["rank_ic"] for r in daily if r["rank_ic"] is not None]
    mses = [r["mse"] for r in daily if r["mse"] is not None]
    return dict(
        requested_dates=len(dates),
        valid_ic_dates=len(ics),
        valid_mse_dates=len(mses),
        mean_daily_ic=math.fsum(ics) / len(ics) if ics else None,
        mean_daily_mse=math.fsum(mses) / len(mses) if mses else None,
        daily=daily,
    )


def selected(candidates):
    best = None
    for candidate in candidates:
        m = candidate.get("metrics")
        if candidate["status"] != "completed" or not m or m["valid_ic_dates"] < 20:
            continue
        ic, mse = m["mean_daily_ic"], m["mean_daily_mse"]
        if ic is None or mse is None:
            continue
        if (
            best is None
            or ic > best["metrics"]["mean_daily_ic"] + 1e-12
            or (
                abs(ic - best["metrics"]["mean_daily_ic"]) <= 1e-12
                and mse < best["metrics"]["mean_daily_mse"]
            )
        ):
            best = candidate
    return best


def verify_candidate_start(candidate):
    if candidate["status"] not in ("completed", "failed") or (
        candidate["status"] == "failed" and not candidate["reason"]
    ):
        raise ValueError("INVALID_TREE_CANDIDATE_START_STATE")
    attempt = candidate["attempt"]
    if attempt is None:
        if (
            candidate["status"] != "failed"
            or candidate["reason"] != "RuntimeError: Fit budget exhausted"
        ):
            raise ValueError("TREE_CANDIDATE_START_MISSING")
    elif type(attempt) is not int or not 1 <= attempt <= 6:
        raise ValueError("INVALID_TREE_CANDIDATE_START")
    if candidate["status"] == "completed" and candidate["reason"] is not None:
        raise ValueError("INVALID_TREE_COMPLETED_CANDIDATE_REASON")


def verify_model_identity(row, end):
    if row["end"] != end or (
        row["model"] == "momentum20" and row["status"] != "completed"
    ):
        raise ValueError("TREE_MODEL_IDENTITY_CHANGED")
    if row["model"] == "shallow_tree" and row["status"] not in (
        "completed",
        "failed",
        "unavailable",
    ):
        raise ValueError("INVALID_TREE_MODEL_STATE")


def verify_reserved_state(binding, output):
    from .study_identity import canonical_hash

    owner = relocated_path(binding["owner"])
    key = canonical_hash(dict(protocol=PROTOCOL, input_sha256=binding["input_sha256"]))
    reservation = owner / "research-reservations" / (key + ".json")
    receipt = read(reservation)
    snapshot = read(owner / "research-reservations" / (key + ".json.tree-started"))
    if (
        set(snapshot) != {"schema", "receipt", "token_sha256", "pid"}
        or snapshot["schema"] != "equity.tree_start.v1"
        or snapshot["receipt"] != receipt
        or type(snapshot["pid"]) is not int
        or snapshot["pid"] <= 0
        or receipt["schema"] != "competition.research_reservation.v1"
        or receipt["status"] != "reserved"
        or relocated_path(receipt["owner_root"]) != owner
        or relocated_path(receipt["output"]) != output
        or receipt["identity"]["binding_sha256"] != binding["binding_sha256"]
        or receipt["identity"]["code_sha256"] != binding["leaf_code_sha256"]
        or receipt["identity"]["lock_sha256"] != binding["locks"]["equity"]
        or receipt["identity"]["protocol"] != PROTOCOL
        or receipt["identity"]["input_sha256"] != binding["input_sha256"]
        or not (owner / "research-reservations" / (key + ".json.started")).is_file()
    ):
        raise ValueError("TREE_RESERVED_START_CHANGED")
    for h in (5, 20):
        marker = read(owner / "research-reservations" / (key + f".json.h{h}.started"))
        if (
            set(marker) != {"schema", "horizon", "pid", "binding_sha256", "output"}
            or marker["schema"] != "equity.tree_horizon_start.v1"
            or marker["horizon"] != h
            or type(marker["pid"]) is not int
            or marker["pid"] <= 0
            or marker["binding_sha256"] != binding["binding_sha256"]
            or relocated_path(marker["output"]) != output / f"h{h}"
        ):
            raise ValueError("TREE_OWNER_HORIZON_START_CHANGED")
        if (
            owner / "research-reservations" / (key + f".json.h{h}.attempts.jsonl")
        ).read_bytes() != (output / f"h{h}/attempts-{h}.jsonl").read_bytes():
            raise ValueError("TREE_OWNER_ATTEMPT_LEDGER_CHANGED")


def paired(accounts, models, windows):
    cells = {
        (r["horizon"], r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"]): r
        for r in accounts
    }
    returns, ranking = [], []
    for h, w, arm, ref, b, fee, delay in product(
        (5, 20),
        windows,
        ("ridge", "elastic_net", "shallow_tree"),
        ("equal_weight", "reversal", "momentum20"),
        (0, 20),
        (0, 20, 40),
        (0, 1),
    ):
        left = cells[h, w, arm, b, fee, delay]
        right = cells[h, w, ref, 0 if ref == "equal_weight" else b, fee, delay]
        comparable = left["metrics"] is not None and right["metrics"] is not None
        returns.append(
            dict(
                horizon=h,
                window=w,
                arm=arm,
                reference=ref,
                buffer=b,
                fee_bps=fee,
                delay=delay,
                difference=left["metrics"]["net_return"]
                - right["metrics"]["net_return"]
                if comparable
                else None,
                reason=None if comparable else "unavailable_account",
                arm_status=left["status"],
                reference_status=right["status"],
            )
        )
    for h, w, arm, ref in product(
        (5, 20),
        windows,
        ("ridge", "elastic_net", "shallow_tree"),
        ("reversal", "momentum20"),
    ):
        left, right = models.get((h, w, arm)), models.get((h, w, ref))
        differences = []
        if left is not None and right is not None:
            for a, b in zip(left["daily"], right["daily"], strict=True):
                if a["date"] != b["date"]:
                    raise ValueError("TREE_PAIRED_DATE_CHANGED")
                if (
                    a["count"] == b["count"]
                    and a["rank_ic"] is not None
                    and b["rank_ic"] is not None
                ):
                    differences.append(a["rank_ic"] - b["rank_ic"])
        ranking.append(
            dict(
                horizon=h,
                window=w,
                arm=arm,
                reference=ref,
                valid_dates=len(differences),
                mean_difference=math.fsum(differences) / len(differences)
                if differences
                else None,
                reason=None if differences else "unavailable_equal_cohort_ic",
            )
        )
    return dict(
        returns=returns,
        rank_ic=ranking,
        equal_weight_rank_ic=dict(
            status="unavailable", reason="constant_equal_weight_scores"
        ),
    )


def verify(protocol):
    binding = verify_binding(protocol, current_source=False)
    parent = relocated_path(binding["parent_equity"])
    output = relocated_path(binding["output"])
    verify_reserved_state(binding, output)
    report = read(output / "report.json")
    fields = {
        "schema",
        "protocol",
        "binding_sha256",
        "status",
        "retrospective",
        "formal_performance_ready",
        "currency",
        "validation_sessions",
        "reused_requested_accounts",
        "new_requested_accounts",
        "models",
        "accounts",
        "fit_attempts",
        "horizons",
        "uncertainty",
        "unavailable_cells",
    }
    if (
        set(report) != fields
        or report["schema"] != "equity.low_turnover_tree.v1"
        or report["protocol"] != PROTOCOL
        or report["binding_sha256"] != binding["binding_sha256"]
        or report["status"] != "completed"
        or report["retrospective"] is not True
        or report["formal_performance_ready"] is not False
        or report["currency"] != "USD"
        or report["validation_sessions"] != 60
        or report["new_requested_accounts"] != 96
        or report["reused_requested_accounts"] != 168
    ):
        raise ValueError("INVALID_TREE_REPORT")
    same(
        report["uncertainty"],
        dict(status="unavailable", reason="uncertainty_tooling_not_validated"),
    )
    same(
        report["horizons"],
        [dict(horizon=h, status="completed", reason=None) for h in (5, 20)],
    )
    same(report["unavailable_cells"], [])
    old = read(parent / "report.json")
    calendar = old["calendar"]
    folds = [calendar[:-21][-80:][:40], calendar[:-21][-80:][40:]]
    windows = {d[0]: d for d in folds}
    observations = load_observations(parent)
    pool = {}
    for row in _csv(
        parent / "decisions.csv",
        ["date", "candidate_id", "session_return", "price_valid"],
    ):
        pool.setdefault(row["date"], {})[row["candidate_id"]] = dict(
            valid=row["price_valid"] == "True",
            session_return=float(row["session_return"])
            if row["session_return"]
            else None,
        )
    model_grid = set(product((5, 20), windows, ("shallow_tree", "momentum20")))
    if (
        len(report["models"]) != 8
        or {(r["horizon"], r["window"], r["model"]) for r in report["models"]}
        != model_grid
    ):
        raise ValueError("TREE_MODEL_GRID_CHANGED")
    common_model = {
        "horizon",
        "window",
        "end",
        "model",
        "status",
        "prediction_rows",
        "metrics",
    }
    tree_extra = {
        "reason",
        "params",
        "candidates",
        "refit_attempt",
        "validation_dates",
        "training_rows",
        "inner_training_rows",
        "decision_at",
        "inner_decision_at",
        "training_latest_label_end",
        "inner_latest_label_end",
    }
    for row in report["models"]:
        if set(row) != common_model | (
            tree_extra if row["model"] == "shallow_tree" else set()
        ):
            raise ValueError("TREE_MODEL_FIELDS_CHANGED")
        verify_model_identity(row, windows[row["window"]][-1])
    predictions, model_metrics, attempts_total = {}, {}, 0
    for h in (5, 20):
        log = output / f"h{h}/attempts-{h}.jsonl"
        if log.stat().st_size > 128 * 1024:
            raise ValueError("TREE_ATTEMPT_LOG_TOO_LARGE")
        lines = [
            read_line for read_line in log.read_text(encoding="utf-8").splitlines()
        ]
        import json

        attempts = [json.loads(line) for line in lines]
        if (
            any(type(r["attempt"]) is not int for r in attempts)
            or len(attempts) > 6
            or [r["attempt"] for r in attempts] != list(range(1, len(attempts) + 1))
        ):
            raise ValueError("TREE_ATTEMPT_BUDGET_CHANGED")
        expected_attempts = []
        for w, dates in windows.items():
            rows = {
                r["model"]: r
                for r in report["models"]
                if r["horizon"] == h and r["window"] == w
            }
            tree = rows["shallow_tree"]
            parent_model = next(
                r
                for r in old["models"]
                if r["horizon"] == h and r["window"] == w and r["model"] == "ridge"
            )
            for key in (
                "decision_at",
                "inner_decision_at",
                "training_latest_label_end",
                "inner_latest_label_end",
                "training_rows",
                "inner_training_rows",
            ):
                same(tree[key], parent_model[key])
            validation = calendar[: calendar.index(w)][-60:]
            same(tree["validation_dates"], validation)
            valid_keys = {
                (d, n)
                for d in validation
                if calendar.index(d) + h < calendar.index(w)
                for n in pool.get(d, {})
                if target(observations, calendar, h, d, n) is not None
            }
            if len(tree["candidates"]) != 2:
                raise ValueError("TREE_CANDIDATE_GRID_CHANGED")
            for depth, candidate in zip((2, 3), tree["candidates"], strict=True):
                if set(candidate) != {
                    "params",
                    "status",
                    "metrics",
                    "reason",
                    "attempt",
                }:
                    raise ValueError("TREE_CANDIDATE_FIELDS_CHANGED")
                same(candidate["params"], dict(max_depth=depth))
                verify_candidate_start(candidate)
                if candidate["attempt"] is not None:
                    expected_attempts.append(
                        dict(
                            attempt=candidate["attempt"],
                            condition=dict(
                                horizon=h,
                                fold=w,
                                model="shallow_tree",
                                phase="validation",
                                params=dict(max_depth=depth),
                            ),
                        )
                    )
                if candidate["status"] == "completed":
                    values = scores(
                        output / f"h{h}/h{h}-{w}-depth{depth}-validation.csv",
                        valid_keys,
                    )
                    # Validation rows exclude labels that have not ended at the outer boundary.
                    valid_pool = {
                        d: {
                            n: r
                            for n, r in pool.get(d, {}).items()
                            if (d, n) in valid_keys
                        }
                        for d in validation
                    }
                    same(
                        candidate["metrics"],
                        metrics(
                            values, valid_pool, observations, calendar, h, validation
                        ),
                    )
                elif (
                    candidate["status"] != "failed"
                    or candidate["metrics"] is not None
                    or not candidate["reason"]
                ):
                    raise ValueError("INVALID_TREE_CANDIDATE_STATE")
            best = selected(tree["candidates"])
            if best is None:
                if (
                    tree["params"] is not None
                    or tree["refit_attempt"] is not None
                    or tree["status"] != "unavailable"
                    or tree["reason"] != "insufficient_valid_validation_dates"
                ):
                    raise ValueError("INVALID_TREE_UNSELECTABLE_STATE")
            else:
                same(tree["params"], best["params"])
                verify_candidate_start(
                    dict(
                        status=tree["status"],
                        attempt=tree["refit_attempt"],
                        reason=tree["reason"],
                    )
                )
            if tree["refit_attempt"] is not None:
                if best is None:
                    raise ValueError("TREE_UNSELECTABLE_REFIT")
                expected_attempts.append(
                    dict(
                        attempt=tree["refit_attempt"],
                        condition=dict(
                            horizon=h,
                            fold=w,
                            model="shallow_tree",
                            phase="refit",
                            params=best["params"],
                        ),
                    )
                )
            expected_keys = {(d, n) for d in dates for n in pool.get(d, {})}
            for arm, row in rows.items():
                key = h, w, arm
                if arm == "momentum20" or row["status"] == "completed":
                    values = scores(
                        output / f"h{h}/h{h}-{w}-{arm}-predictions.csv",
                        expected_keys,
                        missing=arm == "momentum20",
                    )
                    if row["prediction_rows"] != len(values):
                        raise ValueError("TREE_PREDICTION_ROWS_CHANGED")
                    if arm == "momentum20":
                        for (d, n), value in values.items():
                            same(value, momentum(observations, calendar, d, n))
                    elif (
                        best is None
                        or row["params"] != best["params"]
                        or row["refit_attempt"] is None
                    ):
                        raise ValueError("TREE_SELECTION_CHANGED")
                    actual_metrics = metrics(
                        values,
                        pool,
                        observations,
                        calendar,
                        h,
                        dates,
                        ranking=arm == "momentum20",
                    )
                    same(row["metrics"], actual_metrics)
                    model_metrics[key] = actual_metrics
                    predictions[key] = values
                elif (
                    row["status"] not in ("unavailable", "failed")
                    or row["prediction_rows"] != 0
                    or row["metrics"] is not None
                ):
                    raise ValueError("INVALID_TREE_MODEL_STATE")
                else:
                    predictions[key] = None
                    model_metrics[key] = None
        same(attempts, expected_attempts)
        attempts_total += len(attempts)
    if report["fit_attempts"] != attempts_total:
        raise ValueError("TREE_ATTEMPT_COUNT_CHANGED")
    expected = set(
        product(
            (5, 20),
            windows,
            ("shallow_tree", "momentum20"),
            (0, 20),
            (0, 20, 40),
            (0, 1),
        )
    )
    actual = [
        (r["horizon"], r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"])
        for r in report["accounts"]
    ]
    if len(actual) != 96 or set(actual) != expected:
        raise ValueError("TREE_ACCOUNT_GRID_CHANGED")
    checked_plans = {}
    for row in report["accounts"]:
        if set(row) != {
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
            "metrics",
        }:
            raise ValueError("TREE_ACCOUNT_FIELDS_CHANGED")
        h, w, arm, b, fee, delay = (
            row["horizon"],
            row["window"],
            row["arm"],
            row["buffer"],
            row["fee_bps"],
            row["delay"],
        )
        if row["end"] != windows[w][-1]:
            raise ValueError("TREE_WINDOW_END_CHANGED")
        key = h, w, arm, b
        if key not in checked_plans:
            plans = read(output / f"h{h}/h{h}-{w}-{arm}-b{b}-plans.json")
            verify_plans(plans, pool, predictions[h, w, arm], windows[w], h, arm, b)
            checked_plans[key] = plans
        artifact = read(output / f"h{h}" / (name(row) + ".json"))
        if set(artifact) != {"net", "gross"}:
            raise ValueError("TREE_ACCOUNT_ARTIFACT_CHANGED")
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
            same(row[field], artifact["net"][field])
        expected_metrics = (
            net
            | dict(
                gross_return=gross["net_return"],
                cost_drag=gross["net_return"] - net["net_return"],
            )
            if net is not None
            else None
        )
        same(row["metrics"], expected_metrics)
    for row in old["models"]:
        model_metrics[row["horizon"], row["window"], row["model"]] = row["metrics"]
    for h, w in product((5, 20), windows):
        reversal = {
            (d, n): -r["session_return"] if r["session_return"] is not None else None
            for d in windows[w]
            for n, r in pool.get(d, {}).items()
        }
        model_metrics[h, w, "reversal"] = metrics(
            reversal, pool, observations, calendar, h, windows[w], ranking=True
        )
    result = dict(
        schema="competition.low_turnover_tree_verified.v1",
        protocol=PROTOCOL,
        binding_sha256=binding["binding_sha256"],
        retrospective=True,
        formal_performance_ready=False,
        scientific_requirements="all_six_remain_blocked",
        reused_requested_accounts=168,
        new_requested_accounts=96,
        fit_attempts=attempts_total,
        completed_new_accounts=sum(
            r["status"] == "completed" for r in report["accounts"]
        ),
        blocked_new_accounts=sum(r["status"] == "blocked" for r in report["accounts"]),
        uncertainty=report["uncertainty"],
        paired=paired(old["accounts"] + report["accounts"], model_metrics, windows),
    )
    if (output / "verification.json").is_file():
        same(read(output / "verification.json"), result)
    return result
