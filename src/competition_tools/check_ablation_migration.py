"""Check fixed retrospective numerical parity against explicit frozen evidence."""

import argparse
import json
import math
from pathlib import Path
from .datasets.daily_storage import safe_path
from .datasets.storage import write_json
from .evaluation.ablation_catalog import load_origin_evidence, variant_spec
from .evaluation.ablation_runner import verify_plan
from .evaluation.ablation_publication import project_ablation
from .evaluation.study_plan import plan_hash
from .evaluation.study_publication import project_study


def semantic_key(row):
    return (
        row["market"],
        row["strategy"],
        row["variant_id"],
        row["fee_bps"],
        row["fold"]["start"],
        row["fold"]["end"],
        row["manifest_sha256"],
    )


def compare_metric_records(formal, reference):
    def index(rows):
        found = {}
        for r in rows:
            key = semantic_key(r)
            if key in found:
                raise ValueError("DUPLICATE_MIGRATION_RECORD")
            found[key] = r
        return found

    actual, expected = index(formal), index(reference)
    if set(actual) != set(expected):
        raise ValueError("MIGRATION_COVERAGE_MISMATCH")
    maximum = 0.0
    scalars = 0
    for key, r in actual.items():
        a, b = r["metrics"], expected[key]["metrics"]
        if set(a) != set(b):
            raise ValueError("MIGRATION_METRIC_KEYS")
        for name, wanted in b.items():
            value = a[name]
            scalars += 1
            if wanted is None:
                if value is not None:
                    raise ValueError("MIGRATION_NULL_MISMATCH")
            elif type(wanted) is int:
                if type(value) is not int or wanted != value:
                    raise ValueError("MIGRATION_INTEGER_MISMATCH")
            elif type(wanted) is float:
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or not math.isfinite(wanted)
                    or abs(value - wanted) > 1e-10
                ):
                    raise ValueError("MIGRATION_NUMERICAL_MISMATCH")
                maximum = max(maximum, abs(value - wanted))
            else:
                raise ValueError("MIGRATION_METRIC_TYPE")
    return dict(
        matched=len(actual), scalars=scalars, max_abs_error=maximum, tolerance=1e-10
    )


def validate_ablation_migration(
    aggregate_path: Path, parent_aggregate: Path, exploration_root: Path
) -> dict:
    def read(p):
        return json.loads(safe_path(p).read_text(encoding="utf-8"))

    aggregate = read(aggregate_path)
    plan = verify_plan(Path(aggregate["plan_path"]))
    # Reconstruct and verify all private artifacts before comparing saved metrics.
    project_ablation(aggregate)
    parent = read(parent_aggregate)
    project_study(parent)
    old = read(Path(parent["plan_path"]))
    if (
        old["plan_sha256"] != plan_hash(old)
        or old["plan_sha256"] != parent["plan_sha256"]
    ):
        raise ValueError("INVALID_PARENT_PLAN")
    root = safe_path(exploration_root)
    origin = load_origin_evidence(
        dict(
            probe_protocol=str(root / "protocol.json"),
            diagnostic_protocol=str(root / "diagnostic-protocol.json"),
            evidence_manifest=str(root / "evidence-manifest.json"),
        )
    )
    if (
        origin != plan["origin"]
        or read(root / "protocol.json")["parent_plan_sha256"] != old["plan_sha256"]
    ):
        raise ValueError("MIGRATION_ORIGIN_MISMATCH")
    jobs = {j["job_id"]: j for j in plan["jobs"]}
    old_jobs = {j["job_id"]: j for j in old["jobs"]}
    if len(jobs) != 678 or any(r["status"] != "completed" for r in aggregate["jobs"]):
        raise ValueError("MIGRATION_INCOMPLETE")
    formal = [{**jobs[r["job_id"]], "metrics": r["metrics"]} for r in aggregate["jobs"]]
    reference = []
    for r in parent["jobs"]:
        if r["status"] != "completed":
            raise ValueError("MIGRATION_PARENT_INCOMPLETE")
        reference.append(
            {**old_jobs[r["job_id"]], "variant_id": "baseline", "metrics": r["metrics"]}
        )
    for filename in [
        "equity-lab-results.json",
        "crypto-mm-results.json",
        "diagnostic-results.json",
    ]:
        value = read(root / filename)
        for r in value["records"]:
            if r["variant"] == "baseline":
                continue
            parent_job = old_jobs[r["parent_job_id"]]
            normalized = {**r, "variant_id": r["variant"]}
            expected = {**parent_job, "variant_id": r["variant"]}
            if semantic_key(normalized) != semantic_key(expected):
                raise ValueError("MIGRATION_PROBE_PARENT_MISMATCH")
            role = variant_spec(r["market"], r["strategy"], r["variant"])[
                "evidence_role"
            ]
            if (role == "post_hoc_diagnostic") != (
                filename == "diagnostic-results.json"
            ):
                raise ValueError("MIGRATION_ROLE_MISMATCH")
            reference.append(normalized)
    report = compare_metric_records(formal, reference)
    baseline = sum(r["variant_id"] == "baseline" for r in formal)
    post_hoc = sum(r["evidence_role"] == "post_hoc_diagnostic" for r in formal)
    if baseline != 318 or len(formal) - baseline != 360 or post_hoc != 36:
        raise ValueError("MIGRATION_MATRIX_MISMATCH")
    return dict(
        schema="competition.ablation_migration.v1",
        plan_sha256=plan["plan_sha256"],
        origin=origin,
        baseline=baseline,
        new=360,
        post_hoc=post_hoc,
        **report,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["aggregate", "parent-aggregate", "exploration-root", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    destination = safe_path(a.output)
    if destination.exists():
        raise ValueError("MIGRATION_OUTPUT_EXISTS")
    report = validate_ablation_migration(
        a.aggregate, a.parent_aggregate, a.exploration_root
    )
    write_json(destination, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
