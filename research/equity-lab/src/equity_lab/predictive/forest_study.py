"""Separately reserved forest study; prior 264 accounts are never refitted."""

import json
import os
from pathlib import Path

import numpy as np

from .comparison import training_slices
from .data import FEATURES
from .holding import account_name, build_plans
from .holding_account import replay_holdings
from .holding_data import holding_folds, prepare_holding
from .incremental import score_metrics
from .forest_profile import _fit_forest, MODELS, require_real_input
from .tree_study import bind_prepared
from .protocol import Budget, select_candidate

PROTOCOL = "equity.low_turnover_forest.20261031.v1"
REPORT = "equity.low_turnover_forest.v1"


class StudyBudget(Budget):
    """Keep the original budget API while syncing each new start to disk."""

    def __init__(self, path, *, mirror=None, **kwargs):
        kwargs["max_attempts"] = min(kwargs.get("max_attempts", 12), 12)
        super().__init__(path, **kwargs)
        self.mirror = mirror
        if mirror is not None:
            with mirror.open("x", encoding="utf-8"):
                pass

    def begin(self, condition):
        super().begin(condition)
        with self.path.open("ab") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        if self.mirror is not None:
            with self.mirror.open("wb") as stream:
                stream.write(self.path.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def fit_block(
    outer,
    train,
    valid,
    test,
    validation_dates,
    budget,
    horizon,
    window,
    *,
    kind="random_forest",
    fit=None,
    persist=lambda: None,
    result=None,
    candidate_output=None,
):
    if fit is None:
        raise ValueError("FOREST_HORIZON_CLAIM_REQUIRED")
    result = result if result is not None else {}
    result.update(
        status="unavailable",
        reason="insufficient_valid_validation_dates",
        params=None,
        prediction_rows=0,
        metrics=None,
        candidates=[],
        refit_attempt=None,
    )
    for depth in (3, 5):
        row = dict(
            params={"max_depth": depth},
            status="not_started",
            metrics=None,
            reason=None,
            attempt=None,
        )
        result["candidates"].append(row)
        persist()
        try:
            budget.begin(
                dict(
                    horizon=horizon,
                    fold=window,
                    model=kind,
                    phase="validation",
                    params=row["params"],
                )
            )
            row["attempt"] = budget.attempts
            row["status"] = "running"
            persist()
            model = fit(
                kind,
                row["params"],
                train[FEATURES].to_numpy(),
                train.target.to_numpy(),
            )
            prediction = model.predict(valid[FEATURES].to_numpy())
            if not np.isfinite(prediction).all():
                raise ValueError("NONFINITE_VALIDATION_PREDICTION")
            if candidate_output is not None:
                valid[["date", "candidate_id"]].assign(prediction=prediction).to_csv(
                    candidate_output
                    / f"h{horizon}-{window}-{kind}-depth{depth}-validation.csv",
                    index=False,
                    float_format="%.17g",
                )
            row.update(
                status="completed",
                metrics=score_metrics(valid, prediction, validation_dates),
            )
        except Exception as error:
            row.update(status="failed", reason=f"{type(error).__name__}: {error}")
        persist()
    best = select_candidate(result["candidates"])
    values = None
    if best:
        result.update(status="refit_pending", params=best["params"], reason=None)
        persist()
        try:
            budget.begin(
                dict(
                    horizon=horizon,
                    fold=window,
                    model=kind,
                    phase="refit",
                    params=best["params"],
                )
            )
            result["refit_attempt"] = budget.attempts
            result["status"] = "refit_running"
            persist()
            model = fit(
                kind,
                best["params"],
                outer[FEATURES].to_numpy(),
                outer.target.to_numpy(),
            )
            prediction = model.predict(test[FEATURES].to_numpy())
            if not np.isfinite(prediction).all():
                raise ValueError("NONFINITE_FOREST_PREDICTION")
            values = test[["date", "candidate_id"]].assign(prediction=prediction)
            result.update(
                status="completed",
                prediction_rows=len(values),
                metrics=score_metrics(test, prediction, sorted(test.date.unique())),
            )
        except Exception as error:
            result.update(status="failed", reason=f"{type(error).__name__}: {error}")
        persist()
    return result, values


def run_forest_study(
    raw, schedule, output, binding, *, fit=_fit_forest, horizons=(5, 20), claim=None
):
    owner_ledger = None
    if fit is _fit_forest or claim is not None:
        if claim is None:
            raise ValueError("FOREST_HORIZON_CLAIM_REQUIRED")
        from .forest_study_guard import validate_claim

        owner_ledger = validate_claim(claim, binding, output, horizons)
    if fit is _fit_forest:
        require_real_input(binding)
    parent = Path(binding["parent_equity"])
    base, pool, membership = bind_prepared(raw, schedule, parent)
    sessions = base.attrs["sessions"]
    folds = holding_folds(sessions)
    parent_report = json.loads((parent / "report.json").read_text(encoding="utf-8"))
    if (
        parent_report["schema"] != "equity.low_turnover_ml.v2"
        or parent_report["validation_sessions"] != 60
        or parent_report["calendar"] != sessions
        or [
            (r["window"], r["end"])
            for r in parent_report["models"]
            if r["horizon"] == 5 and r["model"] == "ridge"
        ]
        != [(d[0], d[-1]) for d in folds]
    ):
        raise ValueError("PARENT_PROFILE_OR_WINDOWS_CHANGED")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema=REPORT,
        protocol=PROTOCOL,
        status="running",
        retrospective=True,
        formal_performance_ready=False,
        currency="USD",
        binding_sha256=binding["binding_sha256"],
        validation_sessions=60,
        models=[],
        accounts=[],
        fit_attempts=0,
        reused_requested_accounts=264,
        new_requested_accounts=48 * len(horizons),
        uncertainty=dict(
            status="unavailable", reason="uncertainty_tooling_not_validated"
        ),
    )
    budgets = {}

    def persist():
        report["fit_attempts"] = sum(b.attempts for b in budgets.values())
        write(output / "report.json", report)

    persist()
    observations = {
        (r.date, r.candidate_id): dict(
            open=float(r.open_price),
            close=float(r.close_price),
            valid=bool(r.price_valid),
            action_boundary=bool(r.action_boundary),
        )
        for r in base.itertuples()
    }
    try:
        for horizon in horizons:
            local = output / f"attempts-{horizon}.jsonl"
            budget = StudyBudget(
                owner_ledger or local,
                mirror=local if owner_ledger else None,
                max_attempts=12,
                seconds=1200,
            )
            budgets[horizon] = budget
            frame = prepare_holding(raw, schedule, horizon)
            selected = frame.assign(month=frame.date.str[:7]).merge(
                membership[["month", "candidate_id"]],
                on=["month", "candidate_id"],
                how="inner",
            )
            for kind in MODELS:
                for dates in folds:
                    result = dict(
                        horizon=horizon,
                        window=dates[0],
                        end=dates[-1],
                        model=kind,
                    )
                    report["models"].append(result)
                    outer, train, valid, validation_dates = training_slices(
                        selected, sessions, dates, validation_sessions=60
                    )
                    test = selected[selected.date.isin(dates)].copy()
                    result.update(
                        training_rows=len(outer),
                        inner_training_rows=len(train),
                        decision_at=test.decision_at.min().isoformat(),
                        inner_decision_at=selected.loc[
                            selected.date == validation_dates[0], "decision_at"
                        ]
                        .iloc[0]
                        .isoformat(),
                        training_latest_label_end=outer.label_end.max().isoformat(),
                        inner_latest_label_end=train.label_end.max().isoformat(),
                        validation_dates=validation_dates,
                    )
                    result, tree = fit_block(
                        outer,
                        train,
                        valid,
                        test,
                        validation_dates,
                        budget,
                        horizon,
                        dates[0],
                        kind=kind,
                        fit=fit,
                        persist=persist,
                        result=result,
                        candidate_output=output,
                    )
                    if tree is not None:
                        tree.to_csv(
                            output / f"h{horizon}-{dates[0]}-{kind}-predictions.csv",
                            index=False,
                            float_format="%.17g",
                        )
                    for arm, prediction in ((kind, tree),):
                        for buffer in (0, 20):
                            plans = build_plans(
                                pool, prediction, dates, horizon, arm, buffer
                            )
                            write(
                                output
                                / f"h{horizon}-{dates[0]}-{arm}-b{buffer}-plans.json",
                                plans,
                            )
                            for fee in (0, 20, 40):
                                for delay in (0, 1):
                                    identity = dict(
                                        horizon=horizon,
                                        window=dates[0],
                                        end=dates[-1],
                                        arm=arm,
                                        buffer=buffer,
                                        fee_bps=fee,
                                        delay=delay,
                                    )
                                    net = replay_holdings(
                                        observations,
                                        sessions,
                                        dates,
                                        plans,
                                        horizon=horizon,
                                        fee_bps=fee,
                                        delay=delay,
                                    )
                                    gross = replay_holdings(
                                        observations,
                                        sessions,
                                        dates,
                                        plans,
                                        horizon=horizon,
                                        fee_bps=0,
                                        delay=delay,
                                    )
                                    write(
                                        output / (account_name(identity) + ".json"),
                                        dict(net=net, gross=gross),
                                    )
                                    metrics = net["metrics"]
                                    if metrics is not None:
                                        metrics = metrics | dict(
                                            gross_return=gross["metrics"]["net_return"],
                                            cost_drag=gross["metrics"]["net_return"]
                                            - metrics["net_return"],
                                        )
                                    report["accounts"].append(
                                        identity
                                        | {
                                            k: net[k]
                                            for k in (
                                                "status",
                                                "reason",
                                                "blocked_date",
                                                "requested_dates",
                                                "valid_dates",
                                            )
                                        }
                                        | dict(metrics=metrics)
                                    )
                            persist()
        report["status"] = (
            "completed"
            if all(r["status"] == "completed" for r in report["models"])
            else "completed_with_failures"
        )
    except BaseException as error:
        report.update(status="failed", reason=f"{type(error).__name__}: {error}")
        persist()
        raise
    persist()
    return report
