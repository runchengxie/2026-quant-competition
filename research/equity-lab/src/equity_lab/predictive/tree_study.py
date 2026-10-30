"""Opt-in incremental tree study; retained parent accounts are never refitted."""

import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .comparison import training_slices
from .data import FEATURES, monthly_membership, prepare_daily
from .holding import account_name, build_plans
from .holding_account import replay_holdings
from .holding_data import holding_folds, prepare_holding
from .incremental import fit_incremental, score_metrics
from .protocol import Budget, select_candidate

PROTOCOL = "equity.low_turnover_tree.20261031.v1"
REPORT = "equity.low_turnover_tree.v1"


class StudyBudget(Budget):
    """Keep the original budget API while syncing each new start to disk."""

    def __init__(self, path, *, mirror=None, **kwargs):
        super().__init__(path, **kwargs)
        self.mirror = mirror
        if mirror is not None:
            with mirror.open("x", encoding="utf-8"):
                pass

    def begin(self, condition):
        super().begin(condition)
        with self.path.open("a", encoding="utf-8") as stream:
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


def momentum_scores(base, sessions):
    """Close(t)/close(t-20)-1 using the 21 exact completed session marks.

    Candidate identity is the grouping key. A ticker change inside that identity,
    missing calendar observation or known action invalidates the entire lookback.
    The decision is at close(t), so close(t) is available under the parent proxy.
    """
    scores = pd.Series(np.nan, index=base.index, dtype=float)
    for _, group in base.groupby("candidate_id", sort=True):
        grid = group.set_index("date").reindex(sessions)
        valid = grid.price_valid.eq(True) & ~grid.action_boundary.eq(True)
        valid &= grid.close_price.gt(0) & np.isfinite(grid.close_price)
        valid &= ~grid.ticker.fillna("").astype(str).str.strip().isin(
            ["", "nan", "None"]
        )
        complete = valid.rolling(21, min_periods=21).sum().eq(21)
        # Twenty adjacent comparisons cover exactly the 21 marks in this return.
        unchanged = (
            grid.ticker.ne(grid.ticker.shift()).rolling(20, min_periods=20).sum().eq(0)
        )
        values = (grid.close_price / grid.close_price.shift(20) - 1).where(
            complete & unchanged
        )
        scores.loc[group.index] = group.date.map(values).to_numpy()
    return scores


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
    fit=fit_incremental,
    persist=lambda: None,
    result=None,
    candidate_output=None,
):
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
    for depth in (2, 3):
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
                    model="shallow_tree",
                    phase="validation",
                    params=row["params"],
                )
            )
            row["attempt"] = budget.attempts
            row["status"] = "running"
            persist()
            model = fit(
                "tree",
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
                    / f"h{horizon}-{window}-depth{depth}-validation.csv",
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
                    model="shallow_tree",
                    phase="refit",
                    params=best["params"],
                )
            )
            result["refit_attempt"] = budget.attempts
            result["status"] = "refit_running"
            persist()
            model = fit(
                "tree",
                best["params"],
                outer[FEATURES].to_numpy(),
                outer.target.to_numpy(),
            )
            prediction = model.predict(test[FEATURES].to_numpy())
            if not np.isfinite(prediction).all():
                raise ValueError("NONFINITE_TREE_PREDICTION")
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


def export_frames(base, pool, schedule):
    calendar = schedule[["open", "close"]].copy()
    calendar.index = calendar.index.strftime("%Y-%m-%d")
    calendar.index.name = "date"
    observations = base[
        [
            "date",
            "candidate_id",
            "ticker",
            "open_price",
            "close_price",
            "price_valid",
            "action_boundary",
        ]
    ].rename(
        columns={"open_price": "open", "close_price": "close", "price_valid": "valid"}
    )
    decisions = pool[["date", "candidate_id", "session_return", "price_valid"]]
    return {
        "calendar.csv": (calendar, True),
        "observations.csv": (observations, False),
        "decisions.csv": (decisions, False),
    }


def bind_prepared(raw, schedule, parent):
    """Prove input reconstruction matches every retained parent cohort/price row."""
    base = prepare_daily(raw, schedule)
    base["action_boundary"] = (
        base.KnownActionBoundary.eq(True) if "KnownActionBoundary" in base else False
    )
    membership = monthly_membership(base)
    pool = base.assign(month=base.date.str[:7]).merge(
        membership[["month", "candidate_id"]], on=["month", "candidate_id"], how="inner"
    )
    for name, (frame, index) in export_frames(base, pool, schedule).items():
        # Parse both sides identically to tolerate platform newline conventions only.
        generated = io.StringIO(frame.to_csv(index=index, float_format="%.17g"))
        pd.testing.assert_frame_equal(
            pd.read_csv(generated), pd.read_csv(parent / name), check_exact=True
        )
    return base, pool, membership


def run_tree_study(
    raw, schedule, output, binding, *, fit=fit_incremental, horizons=(5, 20), claim=None
):
    owner_ledger = None
    if fit is fit_incremental or claim is not None:
        if claim is None:
            raise ValueError("TREE_HORIZON_CLAIM_REQUIRED")
        from .tree_study_guard import validate_claim

        owner_ledger = validate_claim(claim, binding, output, horizons)
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
        reused_requested_accounts=168,
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
    momentum = pool[["date", "candidate_id"]].merge(
        base[["date", "candidate_id"]].assign(
            prediction=momentum_scores(base, sessions)
        ),
        on=["date", "candidate_id"],
        how="left",
        validate="one_to_one",
    )
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
                max_attempts=6,
                seconds=1200,
            )
            budgets[horizon] = budget
            frame = prepare_holding(raw, schedule, horizon)
            selected = frame.assign(month=frame.date.str[:7]).merge(
                membership[["month", "candidate_id"]],
                on=["month", "candidate_id"],
                how="inner",
            )
            for dates in folds:
                result = dict(
                    horizon=horizon,
                    window=dates[0],
                    end=dates[-1],
                    model="shallow_tree",
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
                    fit=fit,
                    persist=persist,
                    result=result,
                    candidate_output=output,
                )
                if tree is not None:
                    tree.to_csv(
                        output / f"h{horizon}-{dates[0]}-shallow_tree-predictions.csv",
                        index=False,
                        float_format="%.17g",
                    )
                moment = momentum[momentum.date.isin(dates)].copy()
                moment.to_csv(
                    output / f"h{horizon}-{dates[0]}-momentum20-predictions.csv",
                    index=False,
                    float_format="%.17g",
                )
                # Evaluate the same eligible labels; missing lookbacks stay missing.
                moment_scores = (
                    test[["date", "candidate_id"]]
                    .merge(
                        moment,
                        on=["date", "candidate_id"],
                        how="left",
                        validate="one_to_one",
                    )
                    .prediction.to_numpy()
                )
                report["models"].append(
                    dict(
                        horizon=horizon,
                        window=dates[0],
                        end=dates[-1],
                        model="momentum20",
                        status="completed",
                        prediction_rows=len(moment),
                        metrics=score_metrics(test, moment_scores, dates, ranking=True),
                    )
                )
                for arm, prediction in (("shallow_tree", tree), ("momentum20", moment)):
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
