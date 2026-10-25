"""Frozen retrospective multi-session prediction and actual-unit comparisons."""

import json
from pathlib import Path

import numpy as np

from equity_lab.portfolio.rank_buffer import choose
from .comparison import training_slices
from .data import FEATURES, monthly_membership, prepare_daily
from .holding_data import prepare_holding, holding_folds
from .holding_account import replay_holdings
from .protocol import Budget, GRIDS, daily_metrics, fit_model, select_candidate

VARIANTS = [("equal_weight", 0)] + [
    (arm, buffer) for arm in ("reversal", "ridge", "elastic_net") for buffer in (0, 20)
]


def account_name(row):
    return f"h{row['horizon']}-{row['window']}-{row['arm']}-b{row['buffer']}-f{row['fee_bps']}-d{row['delay']}"


def build_plans(pool, predictions, dates, horizon, arm, buffer):
    plans, previous = [], []
    for day in dates[::horizon]:
        current = pool[(pool.date == day) & pool.price_valid.eq(True)]
        row = dict(date=day, selected=[], reason=None)
        try:
            if current.empty:
                raise ValueError("EMPTY_DECISION_POOL")
            if arm == "equal_weight":
                selected = sorted(current.candidate_id.tolist())
            else:
                if arm == "reversal":
                    scores = dict(
                        zip(current.candidate_id, -current.session_return, strict=True)
                    )
                elif predictions is None:
                    raise ValueError("MODEL_UNAVAILABLE")
                else:
                    values = (
                        predictions[predictions.date == day]
                        .set_index("candidate_id")
                        .prediction
                    )
                    scores = {
                        name: float(values.get(name, np.nan))
                        for name in current.candidate_id
                    }
                selected = choose(scores, previous, buffer=buffer)
            row["selected"] = selected
            previous = selected
        except ValueError as error:
            row["reason"] = str(error)
        plans.append(row)
    return plans


def _write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def run_holding(raw, schedule, output, *, profile="legacy"):
    if profile not in ("legacy", "validation60"):
        raise ValueError("UNKNOWN_HOLDING_PROFILE")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    base = prepare_daily(raw, schedule)
    base["action_boundary"] = (
        base.KnownActionBoundary.eq(True) if "KnownActionBoundary" in base else False
    )
    sessions = base.attrs["sessions"]
    calendar_export = schedule[["open", "close"]].copy()
    calendar_export.index = calendar_export.index.strftime("%Y-%m-%d")
    calendar_export.index.name = "date"
    calendar_export.to_csv(output / "calendar.csv")
    folds = holding_folds(sessions)
    membership = monthly_membership(base)
    pool = base.assign(month=base.date.str[:7]).merge(
        membership[["month", "candidate_id"]], on=["month", "candidate_id"], how="inner"
    )
    observations = {
        (row.date, row.candidate_id): dict(
            open=float(row.open_price),
            close=float(row.close_price),
            valid=bool(row.price_valid),
            action_boundary=bool(row.action_boundary),
        )
        for row in base.itertuples()
    }
    exported = base[
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
    exported.to_csv(output / "observations.csv", index=False, float_format="%.17g")
    pool[["date", "candidate_id", "session_return", "price_valid"]].to_csv(
        output / "decisions.csv", index=False, float_format="%.17g"
    )
    report = dict(
        schema="equity.low_turnover_ml.v1",
        status="running",
        retrospective=True,
        formal_performance_ready=False,
        calendar=sessions,
        models=[],
        accounts=[],
        fit_attempts=0,
        currency="USD",
    )
    if profile == "validation60":
        report.update(schema="equity.low_turnover_ml.v2", validation_sessions=60)
    for horizon in (5, 20):
        budget = Budget(
            output / f"attempts-{horizon}.jsonl", max_attempts=28, seconds=1200
        )
        frame = prepare_holding(raw, schedule, horizon)
        selected = frame.assign(month=frame.date.str[:7]).merge(
            membership[["month", "candidate_id"]],
            on=["month", "candidate_id"],
            how="inner",
        )
        for dates in folds:
            outer, train, valid, validation_dates = training_slices(
                selected,
                sessions,
                dates,
                validation_sessions=60 if profile == "validation60" else None,
            )
            test = selected[selected.date.isin(dates)].copy()
            predictions = {}
            for kind, grid in GRIDS.items():
                candidates = []
                for params in grid:
                    budget.begin(
                        dict(
                            horizon=horizon,
                            fold=dates[0],
                            model=kind,
                            phase="validation",
                            params=params,
                        )
                    )
                    candidate = dict(model=kind, params=params, status="failed")
                    try:
                        model = fit_model(
                            kind,
                            params,
                            train[FEATURES].to_numpy(),
                            train.target.to_numpy(),
                        )
                        candidate.update(
                            status="completed",
                            metrics=daily_metrics(
                                valid,
                                model.predict(valid[FEATURES].to_numpy()),
                                validation_dates,
                            ),
                        )
                    except (ValueError, RuntimeError, Warning) as error:
                        candidate["reason"] = type(error).__name__
                    candidates.append(candidate)
                best = select_candidate(candidates)
                result = dict(
                    horizon=horizon,
                    window=dates[0],
                    end=dates[-1],
                    model=kind,
                    status="unavailable",
                    params=None,
                    metrics=None,
                    prediction_rows=0,
                    decision_at=test.decision_at.min().isoformat(),
                    inner_decision_at=selected.loc[
                        selected.date == validation_dates[0], "decision_at"
                    ]
                    .iloc[0]
                    .isoformat(),
                    training_latest_label_end=outer.label_end.max().isoformat(),
                    inner_latest_label_end=train.label_end.max().isoformat(),
                    training_rows=len(outer),
                    inner_training_rows=len(train),
                    candidates=candidates,
                )
                predictions[kind] = None
                if best:
                    budget.begin(
                        dict(
                            horizon=horizon,
                            fold=dates[0],
                            model=kind,
                            phase="refit",
                            params=best["params"],
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
                        values = test[["date", "candidate_id"]].assign(prediction=score)
                        values.to_csv(
                            output / f"h{horizon}-{dates[0]}-{kind}-predictions.csv",
                            index=False,
                            float_format="%.17g",
                        )
                        predictions[kind] = values
                        result.update(
                            status="completed",
                            params=best["params"],
                            prediction_rows=len(values),
                            metrics=daily_metrics(test, score, dates),
                        )
                    except (ValueError, RuntimeError, Warning) as error:
                        result.update(status="failed", reason=type(error).__name__)
                report["models"].append(result)
            for arm, buffer in VARIANTS:
                plans = build_plans(
                    pool, predictions.get(arm), dates, horizon, arm, buffer
                )
                _write(
                    output / f"h{horizon}-{dates[0]}-{arm}-b{buffer}-plans.json", plans
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
                        _write(
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
                            | dict(
                                status=net["status"],
                                reason=net["reason"],
                                blocked_date=net["blocked_date"],
                                requested_dates=net["requested_dates"],
                                valid_dates=net["valid_dates"],
                                metrics=metrics,
                            )
                        )
            report["fit_attempts"] = sum(
                1
                for h in (5, 20)
                if (p := output / f"attempts-{h}.jsonl").exists()
                for _ in p.open(encoding="utf-8")
            )
            _write(output / "report.json", report)
    report["status"] = "completed"
    _write(output / "report.json", report)
    return report
