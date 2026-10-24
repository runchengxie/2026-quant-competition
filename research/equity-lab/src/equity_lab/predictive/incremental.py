"""Fixed retrospective comparisons. Ranking evidence is not trading PnL."""

import json
import math
from pathlib import Path

import numpy as np

from .data import FEATURES, monthly_membership
from .protocol import (
    Budget,
    daily_metrics,
    fit_model,
    outer_blocks,
    select_candidate,
    split_training,
)


def model_specs():
    return [
        {
            "id": name,
            "kind": "ridge",
            "features": features,
            "grid": [{"alpha": a} for a in [0.1, 1.0, 10.0]],
        }
        for name, features in [
            ("ridge_full", FEATURES),
            ("ridge_return_only", ["session_return"]),
            ("ridge_without_return", [f for f in FEATURES if f != "session_return"]),
        ]
    ] + [
        {
            "id": "shallow_tree",
            "kind": "tree",
            "features": FEATURES,
            "grid": [{"max_depth": depth} for depth in (2, 3)],
        }
    ]


def fit_incremental(kind, params, x, y):
    if kind == "ridge":
        return fit_model("ridge", params, x, y)
    if kind != "tree" or params not in ({"max_depth": 2}, {"max_depth": 3}):
        raise ValueError("Unknown incremental model")
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from threadpoolctl import threadpool_limits

    if not len(y) or not np.isfinite(y).all() or np.ptp(y) == 0:
        raise ValueError("Invalid training labels")
    model = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            (
                "model",
                HistGradientBoostingRegressor(
                    **params,
                    loss="squared_error",
                    learning_rate=0.05,
                    max_iter=100,
                    max_leaf_nodes=7,
                    min_samples_leaf=100,
                    l2_regularization=1.0,
                    max_bins=63,
                    random_state=42,
                    early_stopping=False,
                    categorical_features=None,
                ),
            ),
        ]
    )
    with threadpool_limits(limits=2):
        model.fit(x, y)
    return model


def score_metrics(frame, prediction, dates, *, ranking=False):
    result = daily_metrics(frame, prediction, dates)
    if ranking:
        result["mean_daily_mse"] = None
        result["valid_mse_dates"] = 0
        for row in result["daily"]:
            row["mse"] = None
    return result


def descriptive_metrics(frame, prediction, dates, *, eligible=None):
    result = {}
    eligible = frame if eligible is None else eligible
    # Cut points depend on each feature date's eligible universe, never labels.
    for name, column in [
        ("liquidity", "prior_dollar_volume"),
        ("spread", "median_spread"),
    ]:
        ranked = eligible[["date", "candidate_id"]].copy()
        ranked["bin_rank"] = eligible.groupby("date")[column].rank(
            method="average", pct=True
        )
        bins = frame[["date", "candidate_id"]].merge(
            ranked,
            on=["date", "candidate_id"],
            how="left",
            validate="one_to_one",
            sort=False,
        )["bin_rank"]
        bins.index = frame.index
        masks = {
            "low": bins.le(1 / 3),
            "middle": bins.gt(1 / 3) & bins.le(2 / 3),
            "high": bins.gt(2 / 3),
            "missing": bins.isna(),
        }
        result[name] = {
            key: score_metrics(frame.loc[mask], np.asarray(prediction)[mask], dates)
            for key, mask in masks.items()
        }
    result["month"] = {
        month: score_metrics(
            frame[frame.date.str.startswith(month)],
            np.asarray(prediction)[frame.date.str.startswith(month)],
            [d for d in dates if d.startswith(month)],
        )
        for month in sorted({d[:7] for d in dates})
    }
    return result


def paired_metrics(metrics, reference):
    other = {r["date"]: r for r in reference["daily"]}
    rows = []
    for row in metrics["daily"]:
        ref = other[row["date"]]
        difference = (
            row["rank_ic"] - ref["rank_ic"]
            if row["rank_ic"] is not None and ref["rank_ic"] is not None
            else None
        )
        rows.append(
            {
                "date": row["date"],
                "difference": difference,
                "count": row["count"],
                "reference_count": ref["count"],
            }
        )
    valid = [r["difference"] for r in rows if r["difference"] is not None]
    return {
        "daily": rows,
        "valid_dates": len(valid),
        "mean_difference": float(np.mean(valid)) if valid else None,
        "better_dates": sum(x > 0 for x in valid),
    }


def _write(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def run_incremental(frame, sessions, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    budget = Budget(output / "attempts.jsonl", max_attempts=45)
    membership = monthly_membership(frame)
    selected = frame.assign(month=frame.date.str[:7]).merge(
        membership[["month", "candidate_id"]], on=["month", "candidate_id"], how="inner"
    )
    report = {
        "schema": "equity.incremental_private.v1",
        "status": "running",
        "retrospective": True,
        "pnl_available": False,
        "formal_common_stock_ready": False,
        "availability": "bar_close_proxy_unverified",
        "fit_attempts": 0,
        "folds": [],
    }

    def persist():
        report["fit_attempts"] = budget.attempts
        _write(output / "report.json", report)

    persist()
    try:
        for dates in outer_blocks(sessions):
            first = dates[0]
            decision = frame.loc[frame.date == first, "decision_at"].iloc[0]
            training_dates = [d for d in sessions if d < first]
            validation_dates = training_dates[-math.ceil(len(training_dates) * 0.2) :]
            inner_decision = frame.loc[
                frame.date == validation_dates[0], "decision_at"
            ].iloc[0]
            outer_train = split_training(selected, first, decision).dropna(
                subset=["target"]
            )
            train = split_training(outer_train, validation_dates[0], inner_decision)
            valid = outer_train[outer_train.date.isin(validation_dates)]
            test = (
                selected[selected.date.isin(dates)]
                .dropna(subset=["target"])
                .reset_index(drop=True)
            )
            fold = {
                "start": first,
                "end": dates[-1],
                "test_rows": len(test),
                "test_candidate_count": int(test.candidate_id.nunique()),
                "training_rows": len(train),
                "validation_start": validation_dates[0],
                "models": [],
                "candidates": [],
            }
            report["folds"].append(fold)
            baselines = [
                ("constant_zero", np.zeros(len(test)), False),
                ("session_return_rank", test.session_return.to_numpy(), True),
                ("reversal", -test.session_return.to_numpy(), True),
            ]
            for name, prediction, ranking in baselines:
                fold["models"].append(
                    {
                        "model": name,
                        "status": "completed",
                        "metrics": score_metrics(
                            test, prediction, dates, ranking=ranking
                        ),
                    }
                )
            for spec in model_specs():
                features = spec["features"]
                candidates = []
                for params in spec["grid"]:
                    row = {"model": spec["id"], "params": params, "status": "running"}
                    candidates.append(row)
                    fold["candidates"].append(row)
                    budget.begin(
                        {
                            "fold": first,
                            "phase": "validation",
                            "model": spec["id"],
                            "params": params,
                        }
                    )
                    try:
                        model = fit_incremental(
                            spec["kind"],
                            params,
                            train[features].to_numpy(),
                            train.target.to_numpy(),
                        )
                        prediction = model.predict(valid[features].to_numpy())
                        row.update(
                            status="completed",
                            metrics=score_metrics(valid, prediction, validation_dates),
                        )
                    except Exception as error:
                        row.update(
                            status="failed", reason=f"{type(error).__name__}: {error}"
                        )
                    persist()
                best = select_candidate(candidates)
                result = {
                    "model": spec["id"],
                    "status": "unselectable",
                    "reason": "insufficient_inner_dates",
                }
                if best:
                    budget.begin(
                        {
                            "fold": first,
                            "phase": "refit",
                            "model": spec["id"],
                            "params": best["params"],
                        }
                    )
                    try:
                        model = fit_incremental(
                            spec["kind"],
                            best["params"],
                            outer_train[features].to_numpy(),
                            outer_train.target.to_numpy(),
                        )
                        prediction = model.predict(test[features].to_numpy())
                        result.update(
                            status="completed",
                            params=best["params"],
                            metrics=score_metrics(test, prediction, dates),
                            strata=descriptive_metrics(
                                test,
                                prediction,
                                dates,
                                eligible=selected[selected.date.isin(dates)],
                            ),
                        )
                        if spec["kind"] == "ridge":
                            result["standardized_coefficients"] = dict(
                                zip(features, model.named_steps["model"].coef_.tolist())
                            )
                        private = test[["date", "candidate_id", "target"]].copy()
                        private["prediction"] = prediction
                        private.to_parquet(
                            output / f"{first}-{spec['id']}-predictions.parquet",
                            index=False,
                        )
                    except Exception as error:
                        result.update(
                            status="failed", reason=f"{type(error).__name__}: {error}"
                        )
                fold["models"].append(result)
                persist()
            refs = {m["model"]: m for m in fold["models"]}
            for result in fold["models"]:
                if "metrics" in result:
                    result["versus_reversal"] = paired_metrics(
                        result["metrics"], refs["reversal"]["metrics"]
                    )
                    if "metrics" in refs["ridge_full"]:
                        result["versus_ridge"] = paired_metrics(
                            result["metrics"], refs["ridge_full"]["metrics"]
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
