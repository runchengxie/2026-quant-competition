"""Frozen historical ranking-to-cost proxies, with unavailable outcomes retained."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .data import FEATURES, monthly_membership
from .protocol import (
    Budget,
    GRIDS,
    daily_metrics,
    fit_model,
    outer_blocks,
    select_candidate,
    split_training,
)

ARMS = ("equal_weight", "reversal", "ridge", "elastic_net")
FEES = (0, 20, 40)
DELAYS = (0, 1)


def select_weights(identities, predictions, *, top_n=50):
    values = np.asarray(predictions, dtype=float)
    if (
        values.ndim != 1
        or len(values) != len(identities)
        or not len(values)
        or not np.isfinite(values).all()
        or len(set(identities)) != len(identities)
    ):
        raise ValueError("INVALID_SCORES")
    if np.ptp(values) == 0:
        raise ValueError("CONSTANT_SCORES")
    if type(top_n) is not int or not 1 <= top_n <= 50 or len(values) < top_n:
        raise ValueError("INSUFFICIENT_DECISION_POOL")
    chosen = sorted(zip(identities, values, strict=True), key=lambda r: (-r[1], r[0]))[
        :top_n
    ]
    return {identity: 1 / top_n for identity, _ in chosen}


def training_slices(frame, sessions, dates, *, validation_sessions=None):
    training_dates = [day for day in sessions if day < dates[0]]
    if len(training_dates) < 126:
        raise ValueError("INSUFFICIENT_TRAINING_DATES")
    if validation_sessions is not None:
        if type(validation_sessions) is not int or validation_sessions != 60:
            raise ValueError("UNSUPPORTED_VALIDATION_POLICY")
        if len(training_dates) - validation_sessions < 80:
            raise ValueError("INSUFFICIENT_INNER_TRAINING_CALENDAR")
    count = validation_sessions or math.ceil(len(training_dates) * 0.2)
    validation_dates = training_dates[-count:]
    decision = frame.loc[frame.date == dates[0], "decision_at"].iloc[0]
    inner_decision = frame.loc[frame.date == validation_dates[0], "decision_at"].iloc[0]
    outer = split_training(frame, dates[0], decision).dropna(subset=["target"])
    train = split_training(outer, validation_dates[0], inner_decision)
    valid = outer[outer.date.isin(validation_dates)]
    return outer, train, valid, validation_dates


def score_account(
    frame,
    scores,
    dates,
    sessions,
    arm,
    fee_bps,
    delay,
    *,
    decision_pool=None,
    outcomes=None,
):
    if (
        arm not in ARMS
        or type(fee_bps) is not int
        or fee_bps not in FEES
        or type(delay) is not int
        or delay not in DELAYS
        or sessions != sorted(set(sessions))
        or dates != sorted(set(dates))
        or not dates
        or not set(dates) <= set(sessions)
        or frame[["date", "candidate_id"]].duplicated().any()
    ):
        raise ValueError("INVALID_COMPARISON_ACCOUNT")
    if scores is not None and scores[["date", "candidate_id"]].duplicated().any():
        raise ValueError("DUPLICATE_PREDICTION")
    pool = frame if decision_pool is None else decision_pool
    lookup = frame.set_index(["date", "candidate_id"]) if outcomes is None else outcomes
    fee, nav, gross_nav, peak, drawdown = fee_bps / 10000, 1.0, 1.0, 1.0, 0.0
    periods, contributions, costs, daily_returns, turnover = [], {}, [], [], 0.0
    valid_dates, continuous = 0, True
    for day in dates:
        index = sessions.index(day) + 1 + delay
        execution = sessions[index] if index < len(sessions) else None
        row = dict(
            date=day,
            execution_date=execution,
            status="blocked",
            selected=[],
            reason=None,
        )
        current = pool[(pool.date == day) & pool.price_valid.fillna(False)]
        weights = None
        try:
            identities = current.candidate_id.tolist()
            if not identities:
                raise ValueError("EMPTY_DECISION_POOL")
            if arm == "equal_weight":
                weights = {name: 1 / len(identities) for name in identities}
            else:
                if arm == "reversal":
                    predictions = -current.session_return.to_numpy()
                elif scores is None:
                    raise ValueError("MODEL_UNAVAILABLE")
                else:
                    today = scores[scores.date == day].set_index("candidate_id")
                    predictions = today.reindex(identities).prediction.to_numpy()
                weights = select_weights(identities, predictions)
            row["selected"] = sorted(weights)
            if execution is None:
                raise ValueError("MISSING_EXECUTION_SESSION")
            keys = pd.MultiIndex.from_tuples([(execution, name) for name in weights])
            observed = lookup.reindex(keys)
            changes = observed.session_return.to_numpy(dtype=float)
            if (
                not observed.price_valid.eq(True).all()
                or not np.isfinite(changes).all()
            ):
                raise ValueError("MISSING_SELECTED_OUTCOME")
            if (changes <= -1).any():
                raise ValueError("INVALID_SELECTED_RETURN")
            weighted = float(np.dot(list(weights.values()), changes))
            factor = (1 + weighted) * (1 - fee) / (1 + fee)
            if not math.isfinite(factor) or factor <= 0:
                raise ValueError("INVALID_ACCOUNT_EQUITY")
            valid_dates += 1
            row.update(
                status="completed",
                net_return=factor - 1,
                equity=None,
                price_pnl=None,
                cost=None,
            )
            if continuous:
                price_pnl = nav * weighted / (1 + fee)
                cost = nav * fee * (2 + weighted) / (1 + fee)
                after = nav * factor
                if abs(price_pnl - cost - (after - nav)) > 1e-10 * max(1, nav, after):
                    raise ValueError("UNRECONCILED_INTRADAY_PROXY")
                for name, change in zip(weights, changes, strict=True):
                    contributions[name] = contributions.get(name, 0.0) + nav * weights[
                        name
                    ] * change / (1 + fee)
                costs.append(cost)
                turnover += (2 + weighted) / (1 + fee)
                nav, gross_nav = after, gross_nav * (1 + weighted)
                peak = max(peak, nav)
                drawdown = max(drawdown, 1 - nav / peak)
                daily_returns.append(factor - 1)
                row.update(equity=nav, price_pnl=price_pnl, cost=cost)
        except ValueError as error:
            row.update(reason=str(error), status="blocked")
            continuous = False
        periods.append(row)
    metrics = None
    if continuous:
        positive = sum(max(0, value) for value in contributions.values())
        ordered = sorted(
            range(len(daily_returns)), key=lambda i: (-daily_returns[i], i)
        )[:5]
        metrics = dict(
            net_return=nav - 1,
            gross_return=gross_nav - 1,
            cost_drag=gross_nav - nav,
            max_drawdown=drawdown,
            total_costs=math.fsum(costs),
            turnover=turnover,
            top_asset_positive_price_pnl_share=max(contributions.values()) / positive
            if positive
            else None,
            without_best_five_days_return=math.prod(
                1 + value for i, value in enumerate(daily_returns) if i not in ordered
            )
            - 1,
        )
    return dict(
        status="completed" if continuous else "blocked",
        requested_dates=len(dates),
        valid_dates=valid_dates,
        metrics=metrics,
        periods=periods,
        accounting_model="intraday_cash_proxy.v1",
        quote_currency="USD",
        pnl_available=False,
        ex_post_diagnostic=True,
    )


def run_comparison(frame, sessions, output, *, quality):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    budget = Budget(output / "attempts.jsonl", max_attempts=42)
    membership = monthly_membership(frame)
    selected = frame.assign(month=frame.date.str[:7]).merge(
        membership[["month", "candidate_id"]], on=["month", "candidate_id"], how="inner"
    )
    outcomes = frame.set_index(["date", "candidate_id"])
    observed_columns = ["date", "candidate_id", "session_return", "price_valid"]
    frame[observed_columns].to_csv(
        output / "execution-observations.csv", index=False, float_format="%.17g"
    )
    selected[observed_columns].to_csv(
        output / "decision-pool.csv", index=False, float_format="%.17g"
    )
    report = dict(
        schema="equity.strategy_comparison.v1",
        status="running",
        retrospective=True,
        pnl_available=False,
        formal_common_stock_ready=False,
        availability="bar_close_proxy_unverified",
        quality=quality,
        folds=[],
        accounts=[],
        fit_attempts=0,
        calendar=sessions,
    )

    def persist():
        report["fit_attempts"] = budget.attempts
        temporary = output / "report.tmp"
        temporary.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(output / "report.json")

    persist()
    for dates in outer_blocks(sessions[:-1]):
        outer, train, valid, validation_dates = training_slices(
            selected, sessions, dates
        )
        test = selected[selected.date.isin(dates)].copy()
        fold = dict(
            start=dates[0],
            end=dates[-1],
            requested_dates=len(dates),
            models=[],
            candidates=[],
        )
        report["folds"].append(fold)
        predictions = {}
        for kind, grid in GRIDS.items():
            candidates = []
            for params in grid:
                row = dict(model=kind, params=params, status="running")
                candidates.append(row)
                fold["candidates"].append(row)
                budget.begin(
                    dict(fold=dates[0], phase="validation", model=kind, params=params)
                )
                try:
                    model = fit_model(
                        kind,
                        params,
                        train[FEATURES].to_numpy(),
                        train.target.to_numpy(),
                    )
                    row.update(
                        status="completed",
                        metrics=daily_metrics(
                            valid,
                            model.predict(valid[FEATURES].to_numpy()),
                            validation_dates,
                        ),
                    )
                except (ValueError, RuntimeError, Warning) as error:
                    row.update(status="failed", reason=type(error).__name__)
                persist()
            best = select_candidate(candidates)
            result = dict(
                model=kind,
                status="unavailable",
                reason="NO_VALID_INNER_SELECTION",
                metrics=None,
            )
            predictions[kind] = None
            if best:
                budget.begin(
                    dict(
                        fold=dates[0], phase="refit", model=kind, params=best["params"]
                    )
                )
                try:
                    model = fit_model(
                        kind,
                        best["params"],
                        outer[FEATURES].to_numpy(),
                        outer.target.to_numpy(),
                    )
                    score = model.predict(test[FEATURES].to_numpy())
                    prediction = test[["date", "candidate_id", "target"]].assign(
                        prediction=score
                    )
                    prediction.to_parquet(
                        output / f"{dates[0]}-{kind}-predictions.parquet", index=False
                    )
                    prediction[["date", "candidate_id", "prediction"]].to_csv(
                        output / f"{dates[0]}-{kind}-predictions.csv",
                        index=False,
                        float_format="%.17g",
                    )
                    predictions[kind] = prediction
                    result.update(
                        status="completed",
                        reason=None,
                        params=best["params"],
                        metrics=daily_metrics(test, score, dates),
                    )
                except (ValueError, RuntimeError, Warning) as error:
                    result.update(status="failed", reason=type(error).__name__)
            fold["models"].append(result)
            persist()
        for arm in ARMS:
            for fee in FEES:
                for delay in DELAYS:
                    account = score_account(
                        frame,
                        predictions.get(arm),
                        dates,
                        sessions,
                        arm,
                        fee,
                        delay,
                        decision_pool=selected,
                        outcomes=outcomes,
                    )
                    name = f"{dates[0]}-{arm}-{fee}-{delay}.json"
                    (output / name).write_text(
                        json.dumps(account, allow_nan=False), encoding="utf-8"
                    )
                    report["accounts"].append(
                        dict(
                            window=dates[0],
                            end=dates[-1],
                            arm=arm,
                            fee_bps=fee,
                            delay=delay,
                            path=name,
                            **{
                                key: account[key]
                                for key in (
                                    "status",
                                    "requested_dates",
                                    "valid_dates",
                                    "metrics",
                                )
                            },
                        )
                    )
                    persist()
    report["status"] = "completed"
    persist()
    return report
