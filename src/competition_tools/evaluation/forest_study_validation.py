"""Independent stdlib consumer of the separately reserved forest family."""

import json
from itertools import product

from ..project_storage import relocated_path
from .comparison_evidence import _csv
from .holding_reference import verify_holding_account, verify_plans
from .low_turnover_evidence import load_observations
from .forest_study import PROTOCOL, read, verify_binding, _retained_records
from .tree_study_validation import same, name, target, scores, metrics, selected

MODELS = ("random_forest", "extra_trees")
REFERENCES = (
    "equal_weight",
    "reversal",
    "momentum20",
    "ridge",
    "elastic_net",
    "shallow_tree",
)


def paired(accounts, windows):
    cells = {
        (r["horizon"], r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"]): r
        for r in accounts
    }
    result = []
    for h, w, arm, reference, b, fee, delay in product(
        (5, 20), windows, MODELS, REFERENCES, (0, 20), (0, 20, 40), (0, 1)
    ):
        left = cells[h, w, arm, b, fee, delay]
        right = cells[
            h, w, reference, 0 if reference == "equal_weight" else b, fee, delay
        ]
        available = left["metrics"] is not None and right["metrics"] is not None
        result.append(
            dict(
                horizon=h,
                window=w,
                arm=arm,
                reference=reference,
                buffer=b,
                fee_bps=fee,
                delay=delay,
                difference=left["metrics"]["net_return"]
                - right["metrics"]["net_return"]
                if available
                else None,
                reason=None if available else "unavailable_account",
                arm_status=left["status"],
                reference_status=right["status"],
            )
        )
    return result


def verify(protocol):
    binding = verify_binding(protocol, current_source=False)
    output = relocated_path(binding["output"])
    _retained_records(output)
    parent = relocated_path(binding["parent_equity"])
    verify_reserved_state(binding, output)
    report = read(output / "report.json")
    if set(report) != set(
        "schema protocol binding_sha256 status retrospective formal_performance_ready currency validation_sessions reused_requested_accounts new_requested_accounts models accounts fit_attempts horizons uncertainty unavailable_cells".split()
    ):
        raise ValueError("FOREST_REPORT_FIELDS_CHANGED")
    same(
        {
            k: report[k]
            for k in (
                "schema",
                "protocol",
                "binding_sha256",
                "retrospective",
                "formal_performance_ready",
                "currency",
                "validation_sessions",
                "reused_requested_accounts",
                "new_requested_accounts",
                "uncertainty",
            )
        },
        dict(
            schema="equity.low_turnover_forest.v1",
            protocol=PROTOCOL,
            binding_sha256=binding["binding_sha256"],
            retrospective=True,
            formal_performance_ready=False,
            currency="USD",
            validation_sessions=60,
            reused_requested_accounts=264,
            new_requested_accounts=96,
            uncertainty=dict(
                status="unavailable", reason="uncertainty_tooling_not_validated"
            ),
        ),
    )
    # An interrupted worker remains retained engineering evidence; it is never
    # silently converted into a successfully verified complete research family.
    if report["status"] != "completed" or report["unavailable_cells"]:
        raise ValueError("FOREST_INCOMPLETE_RETAIN_ARTIFACTS_AND_OWNER_STARTS")
    same(
        report["horizons"],
        [dict(horizon=h, status="completed", reason=None) for h in (5, 20)],
    )
    old = read(parent / "report.json")
    tree = read(relocated_path(binding["tree_output"]) / "report.json")
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
    model_keys = [(r["horizon"], r["window"], r["model"]) for r in report["models"]]
    if len(model_keys) != 8 or set(model_keys) != set(
        product((5, 20), windows, MODELS)
    ):
        raise ValueError("FOREST_MODEL_GRID_CHANGED")
    predictions, total = {}, 0
    for h in (5, 20):
        log = relocated_path(output / f"h{h}/attempts-{h}.jsonl")
        if log.stat().st_size > 128 * 1024:
            raise ValueError("FOREST_ATTEMPT_LOG_TOO_LARGE")
        attempts = [json.loads(line) for line in log.read_text().splitlines()]
        if len(attempts) > 12:
            raise ValueError("FOREST_ATTEMPT_BUDGET_CHANGED")
        expected = []
        for arm in MODELS:
            for w, dates in windows.items():
                row = next(
                    r
                    for r in report["models"]
                    if (r["horizon"], r["window"], r["model"]) == (h, w, arm)
                )
                if set(row) != set(
                    "horizon window end model status prediction_rows metrics reason params candidates refit_attempt validation_dates training_rows inner_training_rows decision_at inner_decision_at training_latest_label_end inner_latest_label_end".split()
                ):
                    raise ValueError("FOREST_MODEL_FIELDS_CHANGED")
                if row["end"] != dates[-1]:
                    raise ValueError("FOREST_WINDOW_CHANGED")
                reference = next(
                    r
                    for r in old["models"]
                    if (r["horizon"], r["window"], r["model"]) == (h, w, "ridge")
                )
                for key in (
                    "decision_at",
                    "inner_decision_at",
                    "training_latest_label_end",
                    "inner_latest_label_end",
                    "training_rows",
                    "inner_training_rows",
                ):
                    same(row[key], reference[key])
                if (
                    row["training_latest_label_end"] >= row["decision_at"]
                    or row["inner_latest_label_end"] >= row["inner_decision_at"]
                ):
                    raise ValueError("FOREST_UNPURGED_LABELS")
                validation = calendar[: calendar.index(w)][-60:]
                if calendar.index(validation[0]) < 80:
                    raise ValueError("FOREST_INNER_CALENDAR_TOO_SHORT")
                same(row["validation_dates"], validation)
                valid_keys = {
                    (d, n)
                    for d in validation
                    if calendar.index(d) + h < calendar.index(w)
                    for n in pool.get(d, {})
                    if target(observations, calendar, h, d, n) is not None
                }
                if len(row["candidates"]) != 2:
                    raise ValueError("FOREST_CANDIDATE_GRID_CHANGED")
                for depth, candidate in zip((3, 5), row["candidates"], strict=True):
                    if set(candidate) != {
                        "params",
                        "status",
                        "metrics",
                        "reason",
                        "attempt",
                    }:
                        raise ValueError("FOREST_CANDIDATE_FIELDS_CHANGED")
                    same(candidate["params"], dict(max_depth=depth))
                    attempt = candidate["attempt"]
                    if attempt is not None:
                        expected.append(
                            dict(
                                attempt=attempt,
                                condition=dict(
                                    horizon=h,
                                    fold=w,
                                    model=arm,
                                    phase="validation",
                                    params=dict(max_depth=depth),
                                ),
                            )
                        )
                    elif candidate["reason"] != "RuntimeError: Fit budget exhausted":
                        raise ValueError("FOREST_MISSING_START")
                    if candidate["status"] == "completed":
                        if attempt is None or candidate["reason"] is not None:
                            raise ValueError("FOREST_COMPLETED_START_CHANGED")
                        values = scores(
                            output / f"h{h}/h{h}-{w}-{arm}-depth{depth}-validation.csv",
                            valid_keys,
                        )
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
                                values,
                                valid_pool,
                                observations,
                                calendar,
                                h,
                                validation,
                            ),
                        )
                    elif (
                        candidate["status"] != "failed"
                        or not candidate["reason"]
                        or candidate["metrics"] is not None
                    ):
                        raise ValueError("FOREST_INVALID_CANDIDATE_STATE")
                best = selected(row["candidates"])
                if best is None:
                    same(
                        {
                            k: row[k]
                            for k in ("status", "params", "reason", "refit_attempt")
                        },
                        dict(
                            status="unavailable",
                            params=None,
                            reason="insufficient_valid_validation_dates",
                            refit_attempt=None,
                        ),
                    )
                else:
                    same(row["params"], best["params"])
                if row["refit_attempt"] is not None:
                    if best is None:
                        raise ValueError("FOREST_UNSELECTABLE_REFIT")
                    expected.append(
                        dict(
                            attempt=row["refit_attempt"],
                            condition=dict(
                                horizon=h,
                                fold=w,
                                model=arm,
                                phase="refit",
                                params=best["params"],
                            ),
                        )
                    )
                key = h, w, arm
                if row["status"] == "completed":
                    if (
                        best is None
                        or row["refit_attempt"] is None
                        or row["reason"] is not None
                    ):
                        raise ValueError("FOREST_REFIT_START_CHANGED")
                    keys = {(d, n) for d in dates for n in pool.get(d, {})}
                    values = scores(
                        output / f"h{h}/h{h}-{w}-{arm}-predictions.csv", keys
                    )
                    same(row["prediction_rows"], len(keys))
                    same(
                        row["metrics"],
                        metrics(values, pool, observations, calendar, h, dates),
                    )
                    predictions[key] = values
                elif (
                    row["status"] not in ("failed", "unavailable")
                    or row["metrics"] is not None
                    or row["prediction_rows"] != 0
                    or not row["reason"]
                ):
                    raise ValueError("FOREST_INVALID_MODEL_STATE")
                else:
                    predictions[key] = None
        same(attempts, expected)
        if [r["attempt"] for r in attempts] != list(range(1, len(attempts) + 1)):
            raise ValueError("FOREST_ATTEMPT_ORDER_CHANGED")
        total += len(attempts)
    same(report["fit_attempts"], total)
    keys = [
        (r["horizon"], r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"])
        for r in report["accounts"]
    ]
    if len(keys) != 96 or set(keys) != set(
        product((5, 20), windows, MODELS, (0, 20), (0, 20, 40), (0, 1))
    ):
        raise ValueError("FOREST_ACCOUNT_GRID_CHANGED")
    checked = {}
    for row in report["accounts"]:
        if set(row) != set(
            "horizon window end arm buffer fee_bps delay status reason blocked_date requested_dates valid_dates metrics".split()
        ):
            raise ValueError("FOREST_ACCOUNT_FIELDS_CHANGED")
        h, w, arm, b, fee, delay = (
            row[k] for k in ("horizon", "window", "arm", "buffer", "fee_bps", "delay")
        )
        same(row["end"], windows[w][-1])
        key = h, w, arm, b
        if key not in checked:
            plans = read(output / f"h{h}/h{h}-{w}-{arm}-b{b}-plans.json")
            verify_plans(plans, pool, predictions[h, w, arm], windows[w], h, arm, b)
            checked[key] = plans
        artifact = read(output / f"h{h}" / (name(row) + ".json"))
        if set(artifact) != {"net", "gross"}:
            raise ValueError("FOREST_CASH_ARTIFACT_CHANGED")
        net = verify_holding_account(
            artifact["net"],
            observations,
            calendar,
            windows[w],
            checked[key],
            horizon=h,
            fee_bps=fee,
            delay=delay,
        )
        gross = verify_holding_account(
            artifact["gross"],
            observations,
            calendar,
            windows[w],
            checked[key],
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
        same(
            row["metrics"],
            net
            | dict(
                gross_return=gross["net_return"],
                cost_drag=gross["net_return"] - net["net_return"],
            )
            if net is not None
            else None,
        )
    comparisons = paired(
        old["accounts"] + tree["accounts"] + report["accounts"], windows
    )
    if len(comparisons) != 576:
        raise ValueError("FOREST_PAIRED_FAMILY_CHANGED")
    result = dict(
        schema="competition.low_turnover_forest_verified.v1",
        protocol=PROTOCOL,
        binding_sha256=binding["binding_sha256"],
        retrospective=True,
        formal_performance_ready=False,
        scientific_requirements="all_six_remain_blocked",
        reused_requested_accounts=264,
        new_requested_accounts=96,
        combined_requested_accounts=360,
        fit_attempts=total,
        completed_new_accounts=sum(
            r["status"] == "completed" for r in report["accounts"]
        ),
        blocked_new_accounts=sum(r["status"] == "blocked" for r in report["accounts"]),
        uncertainty=report["uncertainty"],
        paired_returns=comparisons,
    )
    if (output / "verification.json").is_file():
        same(read(output / "verification.json"), result)
    return result


def verify_reserved_state(binding, output):
    from .study_identity import canonical_hash

    owner = relocated_path(binding["owner"])
    key = canonical_hash(dict(protocol=PROTOCOL, input_sha256=binding["input_sha256"]))
    reservation = owner / "research-reservations" / (key + ".json")
    receipt = read(reservation)
    snapshot = read(owner / "research-reservations" / (key + ".json.forest-started"))
    if (
        set(snapshot) != {"schema", "receipt", "token_sha256", "pid"}
        or snapshot["schema"] != "equity.forest_start.v1"
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
        raise ValueError("FOREST_RESERVED_START_CHANGED")
    for h in (5, 20):
        marker = read(owner / "research-reservations" / (key + f".json.h{h}.started"))
        if (
            set(marker) != {"schema", "horizon", "pid", "binding_sha256", "output"}
            or marker["schema"] != "equity.forest_horizon_start.v1"
            or marker["horizon"] != h
            or type(marker["pid"]) is not int
            or marker["pid"] <= 0
            or marker["binding_sha256"] != binding["binding_sha256"]
            or relocated_path(marker["output"]) != output / f"h{h}"
        ):
            raise ValueError("FOREST_OWNER_HORIZON_START_CHANGED")
        if (
            relocated_path(
                owner / "research-reservations" / (key + f".json.h{h}.attempts.jsonl")
            ).read_bytes()
            != relocated_path(output / f"h{h}/attempts-{h}.jsonl").read_bytes()
        ):
            raise ValueError("FOREST_OWNER_ATTEMPT_LEDGER_CHANGED")
