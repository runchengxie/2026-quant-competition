"""Stdlib checks for the separately reviewed retrospective aggregate."""

from datetime import date
import hashlib
import json
import re

from .predictive_publication import _keys, _integer, _number, _metrics

REVIEWED_SHA256 = "4959434d1095c5f410a4d58a8c313d7724baaa45ca3a5e86d6eb068884681311"
MODELS = [
    "constant_zero",
    "session_return_rank",
    "reversal",
    "ridge_full",
    "ridge_return_only",
    "ridge_without_return",
    "shallow_tree",
]
ARMS = {
    "daily_trend",
    "daily_matched",
    "weekly_trend",
    "weekly_calendar_matched",
    "weekly_exposure_matched",
}
FEATURES = {
    "session_return",
    "range_fraction",
    "relative_dollar_volume",
    "median_spread",
    "quote_fraction",
    "active_fraction",
}
ACCOUNT_METRICS = "periods net_return gross_return cost_drag volatility sharpe max_drawdown turnover total_costs mean_daily_turnover mean_exposure flat_days"


def validate_public_incremental(data):
    _keys(
        data,
        "schema scientific_commit postprocessing_commit retrospective us_pnl_available formal_common_stock_ready availability equity crypto",
    )
    if (
        data["schema"] != "competition.incremental_research_public.v1"
        or data["retrospective"] is not True
        or data["us_pnl_available"] is not False
        or data["formal_common_stock_ready"] is not False
        or data["availability"] != "bar_close_proxy_unverified"
        or not re.fullmatch("[a-f0-9]{40}", data["scientific_commit"])
        or not re.fullmatch("[a-f0-9]{40}", data["postprocessing_commit"])
    ):
        raise ValueError("Invalid incremental scope")
    equity = data["equity"]
    _keys(equity, "status source_sha256 fit_attempts folds")
    if equity["status"] != "completed" or not re.fullmatch(
        "[a-f0-9]{64}", equity["source_sha256"]
    ):
        raise ValueError("Invalid equity provenance")
    _integer(equity["fit_attempts"], 45, 45)
    if len(equity["folds"]) != 3:
        raise ValueError("Expected three fixed blocks")
    for fold in equity["folds"]:
        _keys(fold, "start end test_rows test_candidate_count models")
        _integer(fold["test_rows"], 0, 10000)
        _integer(fold["test_candidate_count"], 0, fold["test_rows"])
        if [m["model"] for m in fold["models"]] != MODELS:
            raise ValueError("Missing fixed model")
        counts = None
        for model in fold["models"]:
            _keys(model, "model status params metrics strata coefficient_signs")
            if model["status"] != "completed":
                raise ValueError("Unreviewed unavailable model")
            _metrics(model["metrics"], fold["start"], fold["end"])
            observed = [d["count"] for d in model["metrics"]["daily"]]
            if sum(observed) != fold["test_rows"] or (
                counts is not None and observed != counts
            ):
                raise ValueError("Model sample coverage differs")
            counts = observed
            if not max(observed) <= fold["test_candidate_count"] <= fold["test_rows"]:
                raise ValueError("Impossible distinct identity count")
            if (
                model["model"] in {"session_return_rank", "reversal"}
                and model["metrics"]["valid_mse_dates"]
            ):
                raise ValueError("Ranking score is not calibrated return prediction")
            for row in model["strata"]:
                _keys(
                    row,
                    "dimension group mean_daily_ic valid_dates requested_dates rows",
                )
                if row["dimension"] not in {"month", "spread", "liquidity"}:
                    raise ValueError("Unknown descriptive dimension")
                _integer(row["requested_dates"], 0, 20)
                _integer(row["valid_dates"], 0, row["requested_dates"])
                _integer(row["rows"], 0, fold["test_rows"])
                _number(row["mean_daily_ic"], -1, 1, True)
            if not isinstance(model["params"], dict) or not isinstance(
                model["coefficient_signs"], dict
            ):
                raise ValueError("Invalid model description")
            if not set(model["coefficient_signs"]) <= FEATURES or not set(
                model["coefficient_signs"].values()
            ) <= {"positive", "negative", "zero"}:
                raise ValueError("Unknown coefficient sign")
    crypto = data["crypto"]
    _keys(
        crypto,
        "status input_sha256 quote_currency net_simulations gross_simulations jobs",
    )
    if (
        crypto["status"] != "completed"
        or crypto["quote_currency"] != "USDT"
        or not re.fullmatch("[a-f0-9]{64}", crypto["input_sha256"])
    ):
        raise ValueError("Invalid crypto provenance")
    _integer(crypto["net_simulations"], 120, 120)
    _integer(crypto["gross_simulations"], 120, 120)
    if len(crypto["jobs"]) != 120:
        raise ValueError("Invalid replay count")
    keys = set()
    for job in crypto["jobs"]:
        _keys(
            job,
            "window_id start end fee_bps arm metrics actual_rebalances scheduled_rebalances",
        )
        if (
            job["window_id"] != job["start"]
            or (date.fromisoformat(job["end"]) - date.fromisoformat(job["start"])).days
            != 89
        ):
            raise ValueError("Invalid fixed crypto window")
        if (
            type(job["fee_bps"]) is not int
            or job["fee_bps"] not in (35, 50)
            or job["arm"] not in ARMS
        ):
            raise ValueError("Unknown crypto arm/cost")
        key = (job["window_id"], job["fee_bps"], job["arm"])
        if key in keys:
            raise ValueError("Duplicate crypto account")
        keys.add(key)
        _integer(job["scheduled_rebalances"], 1, 90)
        _integer(job["actual_rebalances"], 0, job["scheduled_rebalances"])
        _keys(job["metrics"], ACCOUNT_METRICS)
        for name, value in job["metrics"].items():
            if name in {"periods", "flat_days"}:
                _integer(value, 90 if name == "periods" else 0, 90)
            else:
                _number(value, -1000000, 1000000, name == "sharpe")
    windows = {key[0] for key in keys}
    if len(windows) != 12 or keys != {
        (w, fee, arm) for w in windows for fee in (35, 50) for arm in ARMS
    }:
        raise ValueError("Incomplete paired replay grid")
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != REVIEWED_SHA256:
        raise ValueError("Incremental aggregate differs from reviewed artifact")
    return data
