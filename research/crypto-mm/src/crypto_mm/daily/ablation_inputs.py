"""Independent v2 producer; no root or sibling package imports."""

import json
import re
from pathlib import Path
from .study_inputs import (
    _external,
    _source_hash,
    _load_prices,
    _write,
    _digest,
    _hash,
    _validate_job,
    PARAMETERS,
    JOB_KEYS,
)
from .ablation import evaluate_ablation

EXTRA = {
    "variant_id",
    "variant_parameters",
    "evidence_role",
    "origin",
    "catalog_sha256",
}
ID_KEYS = tuple(sorted((JOB_KEYS | EXTRA) - {"job_id", "plan_sha256"}))


def job_hash(job):
    return _hash({k: job[k] for k in ID_KEYS})


def policy_spec(strategy, variant):
    role = "retrospective_ablation"
    if variant == "baseline" and strategy in {
        "equal_weight",
        "momentum_63d",
        "trend_200d",
    }:
        params = {}
    elif strategy == "trend_200d" and variant == "hysteresis_2pct":
        params = {"band": 0.02}
    elif strategy == "trend_200d" and variant == "vol_target_40pct":
        params = {"lookback_days": 20, "annual_target": 0.4, "annual_periods": 365}
    elif strategy == "trend_200d" and variant == "fixed_exposure_60pct":
        params = {"multiplier": 0.6}
        role = "post_hoc_diagnostic"
    else:
        raise ValueError("INVALID_ABLATION_POLICY")
    return {"variant_id": variant, "variant_parameters": params, "evidence_role": role}


def validate_ablation_job(job):
    try:
        if (
            set(job) != JOB_KEYS | EXTRA
            or job["schema"] != "competition.daily_study_job.v2"
            or job_hash(job) != job["job_id"]
        ):
            raise ValueError
        if any(
            _hash(job[k]) != _hash(v)
            for k, v in policy_spec(job["strategy"], job["variant_id"]).items()
        ):
            raise ValueError
        if any(
            type(job[k]) is not int
            for k in [
                "fee_bps",
                "max_positions",
                "max_gross_exposure",
                "signal_lag_periods",
            ]
        ):
            raise ValueError
        if any(
            type(job["fold"][k]) is not int
            for k in ["warmup_periods", "scoring_periods"]
        ):
            raise ValueError
        origin = job["origin"]
        if (
            set(origin)
            != {
                "probe_protocol_sha256",
                "diagnostic_protocol_sha256",
                "evidence_manifest_sha256",
                "stage",
                "retrospective",
                "accepted_research",
            }
            or origin["stage"] != "retrospective"
            or origin["retrospective"] is not True
            or origin["accepted_research"] is not False
        ):
            raise ValueError
        if any(
            not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v)
            for v in [
                job["catalog_sha256"],
                *(origin[k] for k in origin if k.endswith("sha256")),
            ]
        ):
            raise ValueError
        if _hash(job["parameters"]) != _hash(PARAMETERS[job["strategy"]]):
            raise ValueError
        legacy = {k: v for k, v in job.items() if k not in EXTRA}
        legacy["schema"] = "competition.daily_study_job.v1"
        legacy["job_id"] = _hash(
            {
                k: job[k]
                for k in ("market", "manifest_sha256", "strategy", "fold", "fee_bps")
            }
        )
        _validate_job(legacy)
    except (ValueError, KeyError, TypeError):
        raise ValueError("INVALID_ABLATION_JOB") from None


def run_ablation_job(job_path: Path, output_root: Path) -> dict:
    job = json.loads(_external(job_path).read_text(encoding="utf-8-sig"))
    validate_ablation_job(job)
    code_hash = _source_hash()
    if code_hash != job["expected_leaf_sha256"]:
        raise ValueError("CODE_CHANGED")
    output = _external(output_root)
    if output.exists():
        raise FileExistsError("STUDY_OUTPUT_EXISTS")
    bars = _load_prices(job)
    computation = evaluate_ablation(
        bars,
        job["strategy"],
        job["variant_id"],
        fee_bps=job["fee_bps"],
        quote_currency=job["quote_currency"],
    )
    output.mkdir(parents=True, exist_ok=False)
    periods = output / "periods.json"
    _write(
        periods,
        {
            "schema": "competition.daily_study_periods.v2",
            "job_id": job["job_id"],
            "net": computation["net"]["periods"],
            "gross": computation["gross"]["periods"],
        },
    )
    hold = job["strategy"] in {"buy_hold", "benchmark_buy_hold"} or (
        job["market"] == "crypto" and job["strategy"] == "equal_weight"
    )
    methods = {
        "method_id": job["market"].lower()
        + "."
        + job["strategy"]
        + ".self_financing_daily.v1",
        "strategy": job["strategy"],
        "signal_parameters": PARAMETERS[job["strategy"]],
        "signal_lag_periods": 1,
        "rebalance": "buy_hold" if hold else "daily_target_weights",
        "execution_assumption": "lagged_close_proxy",
        "warmup_periods": 252,
        "scoring_periods": job["fold"]["scoring_periods"],
        "fold_initialization": "independent_cash",
        "cost_model": "self_financing_oneway_bps",
        "terminal_liquidation": False,
        "retrospective": True,
    }
    result = {
        "schema": "competition.daily_study_result.v2",
        "job_id": job["job_id"],
        "plan_sha256": job["plan_sha256"],
        "manifest_sha256": job["manifest_sha256"],
        "code_sha256": code_hash,
        "code_commit": job["code_commit"],
        "market": job["market"],
        "quote_currency": job["quote_currency"],
        "strategy": job["strategy"],
        "parameters": PARAMETERS[job["strategy"]],
        "fee_bps": job["fee_bps"],
        "start": job["fold"]["start"],
        "end": job["fold"]["end"],
        "products": job["products"],
        "fold": job["fold"],
        "methods": methods,
        "metrics": computation["metrics"],
        "benchmark": job["benchmark"],
        "accepted_research": False,
        "artifacts": [
            {
                "path": "periods.json",
                "sha256": _digest(periods),
                "bytes": periods.stat().st_size,
            }
        ],
    }
    for key in EXTRA:
        result[key] = job[key]
    methods.update(
        variant_id=job["variant_id"],
        variant_parameters=job["variant_parameters"],
        evidence_role=job["evidence_role"],
    )
    methods["method_id"] = (
        job["market"].lower()
        + "."
        + job["strategy"]
        + "."
        + job["variant_id"]
        + ".self_financing_daily.v1"
    )
    if job["variant_id"] != "baseline":
        methods["rebalance"] = job["variant_id"]
    _load_prices(job)
    if _source_hash() != code_hash:
        raise ValueError("CODE_CHANGED")
    _write(output / "result.json", result)
    return result
