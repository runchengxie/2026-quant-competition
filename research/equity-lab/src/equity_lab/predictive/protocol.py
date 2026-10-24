"""Frozen retrospective ranking protocol; metrics are not trading profits."""

import json
import math
import time
import warnings
from pathlib import Path

import numpy as np

from .data import FEATURES, monthly_membership

GRIDS = {
    "ridge": [{"alpha": a} for a in [0.1, 1.0, 10.0]],
    "elastic_net": [
        {"alpha": a, "l1_ratio": r}
        for a in [0.0001, 0.001, 0.01]
        for r in [0.1, 0.5, 0.9]
    ],
}


class Budget:
    def __init__(self, path, max_attempts=48, seconds=1200, clock=time.monotonic):
        self.path = Path(path)
        self.clock = clock
        self.started = clock()
        self.seconds = min(seconds, 1200)
        self.limit = min(max_attempts, 48)
        self.attempts = 0
        # Exclusive creation prevents silent restart of an uncertain experiment.
        with self.path.open("x", encoding="utf-8"):
            pass

    def begin(self, condition):
        if self.attempts >= self.limit or self.clock() - self.started >= self.seconds:
            raise RuntimeError("Fit budget exhausted")
        self.attempts += 1
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"attempt": self.attempts, "condition": condition}) + "\n"
            )
            stream.flush()


def outer_blocks(sessions):
    if len(sessions) < 186:
        raise ValueError("Need at least 126 training dates plus 60 test dates")
    if sessions != sorted(set(sessions)):
        raise ValueError("Calendar sessions must be unique and sorted")
    return [sessions[-60 + i * 20 : -60 + (i + 1) * 20 or None] for i in range(3)]


def split_training(frame, first_date, decision):
    return frame[(frame.date < first_date) & (frame.label_end < decision)].copy()


def daily_metrics(frame, predictions, dates):
    values = frame[["date", "candidate_id", "target"]].copy()
    if values[["date", "candidate_id"]].duplicated().any():
        raise ValueError("Duplicate metric candidate/session")
    values["prediction"] = predictions
    daily = []
    for date in dates:
        group = (
            values[values.date == date]
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["prediction", "target"])
        )
        count = len(group)
        mse = float(np.mean((group.prediction - group.target) ** 2)) if count else None
        ic, reason = None, "fewer_than_30_candidates"
        if count >= 30:
            if group.prediction.nunique() <= 1 or group.target.nunique() <= 1:
                reason = "constant_scores_or_labels"
            else:
                ic = float(
                    group.prediction.rank(method="average").corr(
                        group.target.rank(method="average")
                    )
                )
                reason = None
        daily.append(
            {
                "date": date,
                "count": count,
                "mse": mse,
                "rank_ic": ic,
                "ic_reason": reason,
            }
        )
    ics = [r["rank_ic"] for r in daily if r["rank_ic"] is not None]
    mses = [r["mse"] for r in daily if r["mse"] is not None]
    return {
        "requested_dates": len(dates),
        "valid_ic_dates": len(ics),
        "valid_mse_dates": len(mses),
        "mean_daily_ic": float(np.mean(ics)) if ics else None,
        "mean_daily_mse": float(np.mean(mses)) if mses else None,
        "daily": daily,
    }


def select_candidate(rows):
    best = None
    for row in rows:
        metrics = row.get("metrics", {})
        if row["status"] != "completed" or metrics.get("valid_ic_dates", 0) < 20:
            continue
        ic, mse = metrics.get("mean_daily_ic"), metrics.get("mean_daily_mse")
        if ic is None or mse is None or not math.isfinite(ic) or not math.isfinite(mse):
            continue
        if best is None or ic > best["metrics"]["mean_daily_ic"] + 1e-12:
            best = row
        elif (
            abs(ic - best["metrics"]["mean_daily_ic"]) <= 1e-12
            and mse < best["metrics"]["mean_daily_mse"]
        ):
            best = row
    return best


def fit_model(kind, params, x, y):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import ElasticNet, Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits

    if not len(y) or not np.isfinite(y).all() or np.ptp(y) == 0:
        raise ValueError("Empty, invalid or constant training labels")
    estimator = (
        Ridge(**params, solver="cholesky")
        if kind == "ridge"
        else ElasticNet(**params, selection="cyclic", max_iter=2000, tol=1e-4)
    )
    model = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", estimator),
        ]
    )
    with threadpool_limits(limits=2), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        model.fit(x, y)
    return model


def run_pilot(frame, sessions, output, mode):
    if mode != "exploratory_source_candidates":
        raise ValueError(
            "Formal common-stock identity/action/execution acceptance is incomplete"
        )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    budget = Budget(output / "attempts.jsonl")
    membership = monthly_membership(frame)
    selected = frame.assign(month=frame.date.str[:7]).merge(
        membership[["month", "candidate_id"]], on=["month", "candidate_id"], how="inner"
    )
    report = {
        "schema_version": 1,
        "status": "running",
        "mode": mode,
        "scope": "retrospective_source_candidate_prediction",
        "formal_common_stock_ready": False,
        "availability": "bar_close_proxy_unverified",
        "pnl_available": False,
        "features": FEATURES,
        "source_candidate_count": int(frame.candidate_id.nunique()),
        "unresolved_candidate_count": int(
            frame.loc[
                frame.candidate_id.str.startswith("unresolved:"), "candidate_id"
            ].nunique()
        ),
        "membership": membership.to_dict("records"),
        "folds": [],
        "fit_attempts": 0,
        "limitations": [
            "Source selection and survivorship unresolved",
            "Dated type/action coverage incomplete",
            "Observed RTH trades, not executable auction prices",
            "Historical period previously explored",
        ],
    }

    def persist():
        report["fit_attempts"] = budget.attempts
        target = output / "report.json"
        temporary = output / "report.tmp"
        temporary.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(target)

    persist()
    try:
        for dates in outer_blocks(sessions):
            decision = frame.loc[frame.date == dates[0], "decision_at"].iloc[0]
            training_dates = [d for d in sessions if d < dates[0]]
            if len(training_dates) < 126:
                raise ValueError("Need 126 calendar training dates")
            outer_train = split_training(selected, dates[0], decision).dropna(
                subset=["target"]
            )
            validation_dates = training_dates[-math.ceil(len(training_dates) * 0.2) :]
            inner_decision = frame.loc[
                frame.date == validation_dates[0], "decision_at"
            ].iloc[0]
            train = split_training(outer_train, validation_dates[0], inner_decision)
            valid = outer_train[outer_train.date.isin(validation_dates)]
            test = selected[selected.date.isin(dates)].dropna(subset=["target"])
            fold = {
                "start": dates[0],
                "end": dates[-1],
                "training_calendar_dates": len(training_dates),
                "validation_start": validation_dates[0],
                "purged_training_rows": len(train),
                "test_rows": len(test),
                "test_candidate_count": int(test.candidate_id.nunique()),
                "candidates": [],
                "models": [],
                "baselines": [],
            }
            report["folds"].append(fold)
            for kind, grid in GRIDS.items():
                candidates = []
                for params in grid:
                    row = {"model": kind, "params": params, "status": "running"}
                    candidates.append(row)
                    fold["candidates"].append(row)
                    try:
                        budget.begin(
                            {
                                "fold": dates[0],
                                "phase": "validation",
                                "model": kind,
                                "params": params,
                            }
                        )
                        model = fit_model(
                            kind,
                            params,
                            train[FEATURES].to_numpy(),
                            train.target.to_numpy(),
                        )
                        prediction = (
                            model.predict(valid[FEATURES].to_numpy())
                            if len(valid)
                            else np.array([])
                        )
                        row.update(
                            status="completed",
                            metrics=daily_metrics(valid, prediction, validation_dates),
                        )
                    except Exception as error:
                        row.update(
                            status="failed", reason=f"{type(error).__name__}: {error}"
                        )
                    persist()
                best = select_candidate(candidates)
                result = {
                    "model": kind,
                    "status": "unselectable",
                    "reason": "insufficient_valid_inner_dates",
                }
                if best:
                    result = {
                        "model": kind,
                        "params": best["params"],
                        "status": "running",
                    }
                    try:
                        budget.begin(
                            {
                                "fold": dates[0],
                                "phase": "refit",
                                "model": kind,
                                "params": best["params"],
                            }
                        )
                        model = fit_model(
                            kind,
                            best["params"],
                            outer_train[FEATURES].to_numpy(),
                            outer_train.target.to_numpy(),
                        )
                        prediction = (
                            model.predict(test[FEATURES].to_numpy())
                            if len(test)
                            else np.array([])
                        )
                        result.update(
                            status="completed",
                            metrics=daily_metrics(test, prediction, dates),
                        )
                    except Exception as error:
                        result.update(
                            status="failed", reason=f"{type(error).__name__}: {error}"
                        )
                fold["models"].append(result)
            for name, prediction in [
                ("constant_zero", np.zeros(len(test))),
                ("session_return_rank", test.session_return.to_numpy()),
            ]:
                fold["baselines"].append(
                    {"model": name, "metrics": daily_metrics(test, prediction, dates)}
                )
            persist()
        report["status"] = (
            "completed"
            if all(
                m["status"] == "completed" for f in report["folds"] for m in f["models"]
            )
            else "completed_with_failures"
        )
    except Exception as error:
        report.update(status="failed", reason=f"{type(error).__name__}: {error}")
    persist()
    return report
