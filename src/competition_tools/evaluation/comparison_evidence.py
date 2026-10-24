"""Recheck private producer exports before projecting aggregate public facts."""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

from ..datasets.daily_storage import safe_path
from .comparison_reference import (
    verify_equity_account,
    verify_crypto_account,
    rank_ic,
    close,
    validate_identity,
)
from .comparison_publication import validate_cells
from .run_record import verify_run


def read_json(path):
    path = safe_path(path)
    if path.stat().st_size > 8 * 1024**2:
        raise ValueError("COMPARISON_JSON_TOO_LARGE")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("DUPLICATE_COMPARISON_KEY")
            value[key] = item
        return value

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    json.dumps(value, allow_nan=False)
    return value


def _canonical_date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_COMPARISON_DATE")


def _artifact(folder, name):
    path = folder / name
    if path.parent != folder:
        raise ValueError("COMPARISON_ARTIFACT_ESCAPED")
    return read_json(path)


def _csv(path, columns):
    path = safe_path(path)
    if path.stat().st_size > 128 * 1024**2:
        raise ValueError("COMPARISON_CSV_TOO_LARGE")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError("INVALID_COMPARISON_CSV_COLUMNS")
        for index, row in enumerate(reader):
            if index >= 1_000_000 or set(row) != set(columns) or None in row.values():
                raise ValueError("INVALID_COMPARISON_CSV_ROWS")
            yield row


def _observations(path, dates):
    output = {}
    for row in _csv(path, ["date", "candidate_id", "session_return", "price_valid"]):
        if row["date"] not in dates:
            continue
        key = row["date"], row["candidate_id"]
        if key in output or not key[1] or row["price_valid"] not in ("True", "False"):
            raise ValueError("INVALID_COMPARISON_OBSERVATION")
        value = float(row["session_return"]) if row["session_return"] else None
        if value is not None and not math.isfinite(value):
            raise ValueError("NONFINITE_COMPARISON_OBSERVATION")
        output[key] = value if row["price_valid"] == "True" else None
    return output


def _predictions(path, expected):
    output = {}
    for row in _csv(path, ["date", "candidate_id", "prediction"]):
        key = row["date"], row["candidate_id"]
        value = float(row["prediction"])
        if key in output or key not in expected or not math.isfinite(value):
            raise ValueError("INVALID_COMPARISON_PREDICTION")
        output[key] = value
    if set(output) != expected:
        raise ValueError("INCOMPLETE_UNFILTERED_PREDICTIONS")
    return output


def _model_metrics(scores, dates, calendar, observations):
    daily_ics, daily_mses, count = [], [], 0
    for day in dates:
        next_date = calendar[calendar.index(day) + 1]
        pairs = [
            (score, observations.get((next_date, name)))
            for (stamp, name), score in scores.items()
            if stamp == day
        ]
        pairs = [(score, target) for score, target in pairs if target is not None]
        count += len(pairs)
        if pairs:
            daily_mses.append(
                math.fsum((score - target) ** 2 for score, target in pairs) / len(pairs)
            )
        ic = rank_ic([p[0] for p in pairs], [p[1] for p in pairs])
        if ic is not None:
            daily_ics.append(ic)
    return dict(
        valid_ic_dates=len(daily_ics),
        scored_rows=count,
        mean_daily_ic=math.fsum(daily_ics) / len(daily_ics) if daily_ics else None,
        mean_daily_mse=math.fsum(daily_mses) / len(daily_mses) if daily_mses else None,
    )


def _public_row(row, metrics, reasons=None):
    return {
        key: row[key]
        for key in (
            "window",
            "end",
            "arm",
            "fee_bps",
            "delay",
            "status",
            "requested_dates",
            "valid_dates",
        )
    } | dict(metrics=metrics, reasons=[] if reasons is None else reasons)


def verify_equity_export(folder):
    folder = safe_path(folder)
    report = read_json(folder / "report.json")
    if (
        report.get("schema") != "equity.strategy_comparison.v1"
        or report.get("status") != "completed"
        or report.get("retrospective") is not True
        or report.get("pnl_available") is not False
        or report.get("formal_common_stock_ready") is not False
    ):
        raise ValueError("INVALID_EQUITY_COMPARISON_REPORT")
    calendar = report["calendar"]
    if (
        not isinstance(calendar, list)
        or len(calendar) < 187
        or any(not isinstance(day, str) for day in calendar)
        or calendar != sorted(set(calendar))
    ):
        raise ValueError("INVALID_COMPARISON_CALENDAR")
    for day in calendar:
        _canonical_date(day)
    if not isinstance(report.get("accounts"), list) or len(report["accounts"]) != 72:
        raise ValueError("INVALID_COMPARISON_ACCOUNT_GRID")
    first = len(calendar) - 61
    blocks = [calendar[first + i * 20 : first + (i + 1) * 20] for i in range(3)]
    requested = {day for block in blocks for day in block}
    needed = set(calendar[first:])
    observed = _observations(folder / "execution-observations.csv", needed)
    declared = _observations(folder / "decision-pool.csv", requested)
    pool = {
        day: {
            name: value
            for (stamp, name), value in declared.items()
            if stamp == day and value is not None
        }
        for day in requested
    }
    if any(len(names) > 500 for names in pool.values()):
        raise ValueError("COMPARISON_POOL_EXCEEDED")
    folds, predictions, windows = [], {}, {}
    if len(report["folds"]) != 3:
        raise ValueError("COMPARISON_FOLDS_CHANGED")
    for dates, fold in zip(blocks, report["folds"], strict=True):
        if (fold["start"], fold["end"]) != (dates[0], dates[-1]):
            raise ValueError("COMPARISON_WINDOW_CHANGED")
        windows[dates[0]] = dates[-1]
        expected = {key for key in declared if key[0] in dates}
        models = []
        if (
            len(fold["models"]) != 2
            or {m["model"] for m in fold["models"]} != {"ridge", "elastic_net"}
            or len(fold["candidates"]) != 12
        ):
            raise ValueError("COMPARISON_MODEL_GRID_CHANGED")
        for model in fold["models"]:
            scores = None
            metrics = dict(
                valid_ic_dates=0, scored_rows=0, mean_daily_ic=None, mean_daily_mse=None
            )
            if model["status"] == "completed":
                scores = _predictions(
                    folder / f"{dates[0]}-{model['model']}-predictions.csv", expected
                )
                metrics = _model_metrics(scores, dates, calendar, observed)
                for name in ("mean_daily_ic", "mean_daily_mse"):
                    if metrics[name] is None:
                        if model["metrics"][name] is not None:
                            raise ValueError("COMPARISON_MODEL_NULL_CHANGED")
                    else:
                        close(model["metrics"][name], metrics[name])
                if model["metrics"]["valid_ic_dates"] != metrics["valid_ic_dates"]:
                    raise ValueError("COMPARISON_IC_COVERAGE_CHANGED")
            predictions[(dates[0], model["model"])] = scores
            models.append(
                dict(
                    model=model["model"],
                    status=model["status"],
                    params=model.get("params", {}),
                    **metrics,
                )
            )
        folds.append(dict(start=dates[0], end=dates[-1], models=models))
    attempts = (folder / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    if (
        type(report["fit_attempts"]) is not int
        or not 36 <= report["fit_attempts"] <= 42
        or len(attempts) != report["fit_attempts"]
    ):
        raise ValueError("COMPARISON_FIT_BUDGET_CHANGED")
    accounts = []
    for row in report["accounts"]:
        validate_identity(row, "equity")
        name = f"{row['window']}-{row['arm']}-{row['fee_bps']}-{row['delay']}.json"
        if row["window"] not in windows or row["path"] != name:
            raise ValueError("COMPARISON_ARTIFACT_PATH_CHANGED")
        account = _artifact(folder, name)
        if any(
            row[key] != account[key]
            for key in ("status", "requested_dates", "valid_dates", "metrics")
        ):
            raise ValueError("COMPARISON_INDEX_CHANGED")
        dates = next(block for block in blocks if block[0] == row["window"])
        metrics = verify_equity_account(
            row,
            account,
            pool=pool,
            observations=observed,
            scores=predictions.get((row["window"], row["arm"])),
            sessions=calendar,
            dates=dates,
        )
        reasons = sorted(
            {
                period["reason"]
                for period in account["periods"]
                if period["status"] == "blocked"
            }
        )
        accounts.append(_public_row(row, metrics, reasons))
    validate_cells("equity", accounts, windows)
    return dict(
        currency="USD",
        accounting_model="intraday_cash_proxy.v1",
        fit_attempts=report["fit_attempts"],
        folds=folds,
        accounts=accounts,
    )


def verify_crypto_export(folder, batch):
    folder = safe_path(folder)
    report = read_json(folder / "report.json")
    if (
        report.get("schema") != "crypto.strategy_comparison.v1"
        or report.get("status") != "completed"
        or report.get("retrospective") is not True
        or report.get("quote_currency") != "USDT"
    ):
        raise ValueError("INVALID_CRYPTO_COMPARISON_REPORT")
    if batch.get("schema") != "crypto.weekly_input.v1" or not isinstance(
        batch.get("windows"), list
    ):
        raise ValueError("INVALID_COMPARISON_CRYPTO_INPUT")
    for window in batch["windows"]:
        _canonical_date(window["window_id"])
        if window["window_id"] != window["bars"]["dates"][252]:
            raise ValueError("COMPARISON_WINDOW_CHANGED")
    windows = {w["window_id"]: w for w in batch["windows"]}
    if len(windows) != 12 or any(
        len(w["bars"]["close"]) != 8 for w in windows.values()
    ):
        raise ValueError("COMPARISON_CRYPTO_SCOPE_CHANGED")
    if not isinstance(report.get("accounts"), list) or len(report["accounts"]) != 288:
        raise ValueError("INVALID_COMPARISON_ACCOUNT_GRID")
    accounts = []
    for row in report["accounts"]:
        validate_identity(row, "crypto")
        name = f"{row['window']}-{row['arm']}-{row['fee_bps']}-{row['delay']}.json"
        if row["window"] not in windows or row["path"] != name:
            raise ValueError("COMPARISON_ARTIFACT_PATH_CHANGED")
        result = _artifact(folder, name)
        if result["metrics"] != row["metrics"]:
            raise ValueError("COMPARISON_INDEX_CHANGED")
        metrics = verify_crypto_account(row, result, windows[row["window"]]["bars"])
        accounts.append(_public_row(row, metrics))
    validate_cells(
        "crypto",
        accounts,
        {key: window["bars"]["dates"][-1] for key, window in windows.items()},
    )
    if len((folder / "attempts.jsonl").read_text(encoding="utf-8").splitlines()) != 288:
        raise ValueError("COMPARISON_REPLAY_BUDGET_CHANGED")
    return dict(
        currency="USDT",
        accounting_model="self_financing_daily.v1",
        products=8,
        accounts=accounts,
    )


def project_bundle(run_root):
    root = safe_path(run_root)
    result = verify_run(root)
    plan = read_json(root / "experiment-plan.json")
    inputs = {item["path"]: item["sha256"] for item in plan["inputs"]}
    for market, name in (("equity", "equity.parquet"), ("crypto", "crypto.json")):
        report = read_json(root / market / "report.json")
        if (
            report.get("source_sha256") != inputs[f"inputs/{name}"]
            or report.get("source_unchanged") is not True
        ):
            raise ValueError("COMPARISON_INPUT_IDENTITY_CHANGED")
    quality = read_json(root / "inputs/quality.json")
    if read_json(root / "equity/report.json")["quality"] != quality["daily"]:
        raise ValueError("COMPARISON_QUALITY_CHANGED")
    receipt = read_json(root / "inputs/input-receipt.json")
    conversion = dict(
        status=receipt["owner_reported_status"],
        days=receipt["owner_reported_days"],
        rows=receipt["owner_reported_rows"],
        parquet_bytes=receipt["owner_reported_parquet_bytes"],
        independently_verified=False,
    )
    return dict(
        schema="competition.strategy_comparison_public.v1",
        retrospective=True,
        formal_performance_ready=False,
        scientific=dict(
            commit=plan["code"]["commit"],
            plan_sha256=plan["plan_sha256"],
            result_sha256=result["result_sha256"],
            equity_input_sha256=inputs["inputs/equity.parquet"],
            crypto_input_sha256=inputs["inputs/crypto.json"],
        ),
        equity=verify_equity_export(root / "equity"),
        crypto=verify_crypto_export(
            root / "crypto", read_json(root / "inputs/crypto.json")
        ),
        data_quality=quality | dict(conversion=conversion),
        future=read_json(root / "inputs/prospective.json"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    value = project_bundle(args.run_root)
    target = safe_path(args.output)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(status="projected", retrospective=True, formal_performance_ready=False)
        )
    )


if __name__ == "__main__":
    main()
