"""Freeze complete paired folds without changing legacy experiment identities."""

from datetime import datetime, timezone
from pathlib import Path

from ...datasets.daily_storage import safe_path
from ...datasets.storage import digest, write_json
from ..study_inputs import load_study_input
from ..study_identity import source_hash, tree_hash
from .catalog import CATALOG_SHA256, arm_spec
from .contracts import validate_spec, validate_job, job_hash, plan_hash
from .source import snapshot_source


def freeze_controls(spec: dict, output_root: Path, *, code_identity: dict) -> dict:
    validate_spec(spec)
    source = Path(code_identity["source_root"])
    if source_hash(source) != code_identity["source_sha256"]:
        raise ValueError("CONTROLS_SOURCE_CHANGED")
    out = safe_path(output_root)
    if out.exists():
        raise FileExistsError("CONTROLS_OUTPUT_EXISTS")
    inputs = {}
    for market, name in spec["manifests"].items():
        path = safe_path(Path(name))
        if digest(path) != spec["expected_input_hashes"][market]:
            raise ValueError("CONTROLS_INPUT_CHANGED")
        data = load_study_input(path)
        if (
            data["market"] != market
            or data["manifest_sha256"] != spec["expected_input_hashes"][market]
        ):
            raise ValueError("CONTROLS_INPUT_CHANGED")
        inputs[market] = data
    jobs = []
    for market, data in inputs.items():
        dates = data["dates"]
        score = 63 if market == "US" else 90
        if len(dates) < 252 + score:
            raise ValueError("INSUFFICIENT_CONTROLS_HISTORY")
        project = "equity-lab" if market == "US" else "crypto-mm"
        leaf_hash = tree_hash(source / "research" / project / "src")
        for first in range(252, len(dates) - score + 1, score):
            selected = dates[first - 252 : first + score]
            fold = dict(
                warmup_start=selected[0],
                start=selected[252],
                end=selected[-1],
                warmup_periods=252,
                scoring_periods=score,
            )
            for arm in spec["arms"][market]:
                policy = arm_spec(market, arm)
                for fee in spec["costs"][market]:
                    job = dict(
                        schema="competition.strategy_controls_job.v1",
                        market=market,
                        project=project,
                        arm_id=arm,
                        parameters=policy["parameters"],
                        evidence_role=policy["role"],
                        catalog_sha256=CATALOG_SHA256,
                        products=data["products"],
                        benchmark=data["benchmark"],
                        quote_currency=data["quote_currency"],
                        dates=selected,
                        fold=fold,
                        manifest=data["manifest"],
                        manifest_sha256=data["manifest_sha256"],
                        input_files=data["input_files"],
                        input_slice=data["slice"],
                        expected_leaf_sha256=leaf_hash,
                        fee_bps=fee,
                        accounting_model="self_financing_daily.v1",
                        execution_assumption="lagged_close_proxy",
                        accepted_research=False,
                        code_commit=code_identity["commit"],
                    )
                    job["job_id"] = job_hash(job)
                    jobs.append(job)
    if len(jobs) > spec["budget"]["jobs"]:
        raise ValueError("CONTROLS_JOB_BUDGET")
    # Retain committed, exact executed bytes before writing a runnable protocol.
    out.mkdir(parents=True, exist_ok=False)
    receipt = snapshot_source(source, out / "source-snapshot")
    scientific_files = [
        {"path": p.relative_to(source).as_posix(), "sha256": digest(p)}
        for directory in ("src", "research/equity-lab/src", "research/crypto-mm/src")
        for p in sorted((source / directory).rglob("*.py"))
    ]
    value = dict(
        schema="competition.strategy_controls_plan.v1",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        code_commit=code_identity["commit"],
        source_sha256=code_identity["source_sha256"],
        source_snapshot=receipt,
        scientific_source_files=scientific_files,
        catalog_sha256=CATALOG_SHA256,
        inputs=inputs,
        jobs=jobs,
    )
    value["plan_sha256"] = plan_hash(value)
    for job in jobs:
        job["plan_sha256"] = value["plan_sha256"]
        validate_job(job)
    write_json(out / "plan.json", value)
    return value
