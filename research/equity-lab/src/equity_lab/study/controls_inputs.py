"""Standalone controls producer: no root-package or sibling-checkout imports."""

import json
import re
from pathlib import Path

from .inputs import _external, _source_hash, _load_prices, _write, _digest, _hash
from .controls import ARMS, evaluate_control

CATALOG_SHA256 = "6c9238834ef40718c5359f2be631e07bcfc3c8311a4e5634d343918f27bbcddc"
JOB_KEYS = set(
    "schema market project arm_id parameters evidence_role catalog_sha256 products benchmark quote_currency dates fold manifest manifest_sha256 input_files input_slice expected_leaf_sha256 fee_bps accounting_model execution_assumption accepted_research code_commit job_id plan_sha256".split()
)


def policy_spec(arm_id):
    if arm_id not in ARMS:
        raise ValueError("INVALID_EQUITY_CONTROL_POLICY")
    parameters = dict(
        signal="momentum_20d" if arm_id.startswith("mom20") else "equal_weight",
        schedule="monthly" if "monthly" in arm_id else "daily",
    )
    if arm_id.endswith("buffer20"):
        parameters.update(buffer_l1=0.20, include_cash=True, scheduled_cash_exit=True)
    return {"parameters": parameters, "role": "retrospective_control"}


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
            job["market"] != "US"
            or job["project"] != "equity-lab"
            or job["quote_currency"] != "USD"
            or job["benchmark"] != "SPY"
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
            or job["fee_bps"] not in (20, 40)
            or job["accounting_model"] != "self_financing_daily.v1"
            or job["execution_assumption"] != "lagged_close_proxy"
        ):
            raise ValueError
        dates, products, fold = job["dates"], job["products"], job["fold"]
        if (
            not isinstance(dates, list)
            or len(dates) != 315
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
                scoring_periods=63,
            )
        ):
            raise ValueError
        if (
            not isinstance(products, list)
            or not 1 <= len(products) <= 10
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
        raise ValueError("INVALID_EQUITY_CONTROLS_JOB") from None
    return job


def run_controls_job(job_path: Path, output_root: Path) -> dict:
    job = validate_controls_job(read_json(job_path))
    if _source_hash() != job["expected_leaf_sha256"]:
        raise ValueError("CODE_CHANGED")
    out = _external(output_root)
    if out.exists():
        raise FileExistsError("CONTROLS_OUTPUT_EXISTS")
    # Only reuse validated file loading; the new controls job keeps its own schema.
    request = job | {"strategy": policy_spec(job["arm_id"])["parameters"]["signal"]}
    bars = _load_prices(request)
    computation = evaluate_control(
        bars, job["arm_id"], fee_bps=job["fee_bps"], quote_currency="USD"
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
