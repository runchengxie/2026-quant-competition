"""Standalone controls producer: no root-package or sibling-checkout imports."""

import json
import re
from pathlib import Path

from .study_inputs import _external, _source_hash, _load_prices, _write, _digest, _hash
from .controls import LEGACY, STRICT, evaluate_control

CATALOG_SHA256 = "6c9238834ef40718c5359f2be631e07bcfc3c8311a4e5634d343918f27bbcddc"
JOB_KEYS = set(
    "schema market project arm_id parameters evidence_role catalog_sha256 products benchmark quote_currency dates fold manifest manifest_sha256 input_files input_slice expected_leaf_sha256 fee_bps accounting_model execution_assumption accepted_research code_commit job_id plan_sha256".split()
)


def policy_spec(arm_id):
    if arm_id not in LEGACY and arm_id not in STRICT:
        raise ValueError("INVALID_CRYPTO_CONTROL_POLICY")
    parameters = {}
    if arm_id.endswith("strict") or arm_id == "ew_trend_gross_matched":
        parameters = dict(
            lookback_days=20,
            annual_target=0.4,
            annual_periods=365,
            leverage_cap=1.0,
            zero_volatility="cash",
            sample_ddof=1,
        )
        if arm_id == "ew_trend_gross_matched":
            parameters["exposure_source_arm"] = "trend200_vol40_strict"
    elif arm_id == "ew_fixed60":
        parameters = {"multiplier": 0.6}
    return {
        "parameters": parameters,
        "role": "post_hoc_diagnostic"
        if arm_id == "trend200_fixed60_legacy"
        else "retrospective_control",
    }


def read_json(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("DUPLICATE_CONTROLS_KEY")
            value[key] = item
        return value

    def nonfinite(_):
        raise ValueError("NONFINITE_CONTROLS_JSON")

    value = json.loads(
        _external(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=pairs,
        parse_constant=nonfinite,
    )
    json.dumps(value, allow_nan=False)
    return value


def validate_controls_job(job):
    from datetime import date

    try:
        if (
            not isinstance(job, dict)
            or set(job) != JOB_KEYS
            or job["schema"] != "competition.strategy_controls_job.v1"
        ):
            raise ValueError
        if (
            job["market"] != "crypto"
            or job["project"] != "crypto-mm"
            or job["quote_currency"] != "USDT"
            or job["benchmark"] != "equal_weight"
            or job["accepted_research"] is not False
        ):
            raise ValueError
        policy = policy_spec(job["arm_id"])
        if (
            _hash(job["parameters"]) != _hash(policy["parameters"])
            or job["evidence_role"] != policy["role"]
            or job["catalog_sha256"] != CATALOG_SHA256
        ):
            raise ValueError
        for key in ("job_id", "plan_sha256", "manifest_sha256", "expected_leaf_sha256"):
            if not isinstance(job[key], str) or not re.fullmatch(
                "[a-f0-9]{64}", job[key]
            ):
                raise ValueError
        if not isinstance(job["code_commit"], str) or not re.fullmatch(
            "[a-f0-9]{40}", job["code_commit"]
        ):
            raise ValueError
        if job["job_id"] != _hash(
            {k: v for k, v in job.items() if k not in {"job_id", "plan_sha256"}}
        ):
            raise ValueError
        if (
            type(job["fee_bps"]) is not int
            or job["fee_bps"] not in (0, 10, 25)
            or job["accounting_model"] != "self_financing_daily.v1"
            or job["execution_assumption"] != "lagged_close_proxy"
        ):
            raise ValueError
        dates, products, fold = job["dates"], job["products"], job["fold"]
        if (
            not isinstance(dates, list)
            or len(dates) != 342
            or dates != sorted(set(dates))
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
        ):
            raise ValueError
        if _hash(fold) != _hash(
            dict(
                warmup_start=dates[0],
                start=dates[252],
                end=dates[-1],
                warmup_periods=252,
                scoring_periods=90,
            )
        ):
            raise ValueError
        if (
            not isinstance(products, list)
            or not 1 <= len(products) <= 20
            or len(set(products)) != len(products)
            or any(
                not isinstance(p, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", p)
                for p in products
            )
        ):
            raise ValueError
        _hash(job)
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("INVALID_CRYPTO_CONTROLS_JOB") from None
    return job


def run_controls_job(job_path: Path, output_root: Path) -> dict:
    job = validate_controls_job(read_json(job_path))
    if _source_hash() != job["expected_leaf_sha256"]:
        raise ValueError("CODE_CHANGED")
    out = _external(output_root)
    if out.exists():
        raise FileExistsError("CONTROLS_OUTPUT_EXISTS")
    # Only reuse validated file loading; the new controls job keeps its own schema.
    request = job | {"strategy": "equal_weight"}
    bars = _load_prices(request)
    computation = evaluate_control(
        bars, job["arm_id"], fee_bps=job["fee_bps"], quote_currency="USDT"
    )
    if _load_prices(request) != bars or _source_hash() != job["expected_leaf_sha256"]:
        raise ValueError("CONTROLS_INPUT_OR_SOURCE_CHANGED")
    out.mkdir(parents=True, exist_ok=False)
    periods = dict(
        schema="competition.strategy_controls_periods.v1",
        job_id=job["job_id"],
        plan_sha256=job["plan_sha256"],
        net=computation["net"]["periods"],
        gross=computation["gross"]["periods"],
    )
    _write(out / "periods.json", periods)
    result = {
        k: job[k]
        for k in "job_id plan_sha256 manifest_sha256 expected_leaf_sha256 code_commit market arm_id fee_bps quote_currency accepted_research".split()
    }
    result.update(
        schema="competition.strategy_controls_result.v1",
        status="completed",
        metrics=computation["metrics"],
        diagnostics=computation["diagnostics"],
        artifacts=[
            dict(
                path="periods.json",
                bytes=(out / "periods.json").stat().st_size,
                sha256=_digest(out / "periods.json"),
            )
        ],
        issue_codes=[],
    )
    _write(out / "result.json", result)
    return result
