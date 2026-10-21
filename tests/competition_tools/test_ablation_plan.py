"""Versioned policy catalogs must not relax legacy contracts."""

import copy
import pytest
from competition_tools.evaluation.ablation_catalog import (
    variant_spec,
    validate_ablation_spec,
    load_origin_evidence,
)
from competition_tools.evaluation.ablation_plan import (
    ablation_plan_hash,
    validate_ablation_job,
)
from competition_tools.evaluation.study_plan import COSTS, freeze_study


def valid_spec():
    return {
        "schema": "competition.evaluation_spec.v3",
        "manifests": ["input.json"],
        "costs": copy.deepcopy(COSTS),
        "variants": {
            "crypto": [
                {"strategy": s, "variant_id": "baseline"}
                for s in ["equal_weight", "momentum_63d", "trend_200d"]
            ]
            + [{"strategy": "trend_200d", "variant_id": "fixed_exposure_60pct"}]
        },
        "origin": {
            "probe_protocol": "a",
            "diagnostic_protocol": "b",
            "evidence_manifest": "c",
        },
    }


def test_v3_freeze_is_distinct_and_legacy_rejects_variant_fields(tmp_path):
    spec = valid_spec()
    assert validate_ablation_spec(spec) == spec
    with pytest.raises(ValueError, match="INVALID_STUDY_SPEC"):
        freeze_study(
            {**spec, "schema": "competition.evaluation_spec.v2"},
            tmp_path / "out",
            code_identity={},
        )
    for change in [{"extra": True}, {"costs": {**COSTS, "crypto": [False, 10, 25]}}]:
        with pytest.raises(ValueError):
            validate_ablation_spec({**spec, **change})
    for pair in [
        {"strategy": "trend_200d", "variant_id": "unknown"},
        {"strategy": "trend_200d", "variant_id": "baseline", "extra": True},
        spec["variants"]["crypto"][0],
    ]:
        bad = copy.deepcopy(spec)
        bad["variants"]["crypto"].append(pair)
        with pytest.raises(ValueError):
            validate_ablation_spec(bad)
    assert (
        variant_spec("crypto", "trend_200d", "fixed_exposure_60pct")["evidence_role"]
        == "post_hoc_diagnostic"
    )
    with pytest.raises(ValueError):
        variant_spec("US", "trend_200d", "weekly")


def test_plan_hash_binds_variant_origin_and_parameters():
    plan = {
        "jobs": [{"variant_id": "weekly", "plan_sha256": "old"}],
        "origin": {"sha256": "a"},
    }
    h = ablation_plan_hash(plan)
    plan["jobs"][0]["plan_sha256"] = "new"
    assert ablation_plan_hash(plan) == h
    plan["jobs"][0]["variant_id"] = "monthly"
    assert ablation_plan_hash(plan) != h
    with pytest.raises(ValueError):
        validate_ablation_job({"schema": "competition.daily_study_job.v2"})


def test_origin_requires_hashed_protocols_and_safe_members(tmp_path):
    import json
    import hashlib

    a = tmp_path / "protocol.json"
    b = tmp_path / "diagnostic-protocol.json"
    m = tmp_path / "manifest.json"
    for p in [a, b]:
        p.write_text(
            json.dumps(
                {
                    "retrospective": True,
                    "accepted_research": False,
                    "parent_plan_sha256": "a" * 64,
                }
            )
        )
    b.write_text(
        json.dumps(
            {
                "post_hoc": True,
                "accepted_research": False,
                "parent_protocol_sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            }
        )
    )
    m.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": p.name,
                        "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in [a, b]
                ]
            }
        )
    )
    origin = dict(
        probe_protocol=str(a), diagnostic_protocol=str(b), evidence_manifest=str(m)
    )
    assert len(load_origin_evidence(origin)["evidence_manifest_sha256"]) == 64
    b.write_text("{}")
    with pytest.raises(ValueError):
        load_origin_evidence(origin)


def test_freeze_two_synthetic_markets_and_job_integrity(tmp_path):
    from pathlib import Path
    from competition_tools.check_study_delivery import synthetic_manifest
    from competition_tools.evaluation.ablation_plan import freeze_ablation
    from competition_tools.evaluation.study_identity import source_identity
    from test_ablation_source import fixture_repo
    import json
    import hashlib

    root = fixture_repo(tmp_path / "repo")
    # The source fixture need not import either independent package.
    manifests = [
        synthetic_manifest(tmp_path / "stock", crypto=False),
        synthetic_manifest(tmp_path / "crypto", crypto=True),
    ]
    a = tmp_path / "protocol.json"
    b = tmp_path / "diagnostic-protocol.json"
    m = tmp_path / "evidence.json"
    for p in [a, b]:
        p.write_text(
            json.dumps(
                {
                    "retrospective": True,
                    "accepted_research": False,
                    "parent_plan_sha256": "a" * 64,
                }
            )
        )
    b.write_text(
        json.dumps(
            {
                "post_hoc": True,
                "accepted_research": False,
                "parent_protocol_sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            }
        )
    )
    m.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": p.name,
                        "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in [a, b]
                ]
            }
        )
    )
    spec = valid_spec()
    spec["manifests"] = list(map(str, manifests))
    spec["variants"]["US"] = [
        {"strategy": s, "variant_id": "baseline"}
        for s in [
            "buy_hold",
            "equal_weight",
            "momentum_20d",
            "sma_cross",
            "benchmark_buy_hold",
        ]
    ] + [{"strategy": "sma_cross", "variant_id": "weekly"}]
    spec["origin"] = {
        "probe_protocol": str(a),
        "diagnostic_protocol": str(b),
        "evidence_manifest": str(m),
    }
    plan = freeze_ablation(spec, tmp_path / "run", code_identity=source_identity(root))
    assert plan["budget"] == {"jobs": 768, "seconds": 3600, "batch_jobs": 384}
    assert plan["plan_sha256"] == ablation_plan_hash(plan)
    planned = [j for j in plan["jobs"] if j["status"] == "planned"]
    assert {j["market"] for j in planned} == {"US", "crypto"}
    for job in planned:
        validate_ablation_job(job)
    bad = copy.deepcopy(planned[0])
    bad["evidence_role"] = "forward_validated"
    with pytest.raises(ValueError):
        validate_ablation_job(bad)
    import jsonschema

    schemas = Path(__file__).resolve().parents[2] / "schemas/research"
    jsonschema.validate(
        plan, json.loads((schemas / "study-plan.v2.schema.json").read_text())
    )
    for job in planned:
        jsonschema.validate(
            job, json.loads((schemas / "daily-study-job.v2.schema.json").read_text())
        )


def test_v3_schema_rejects_unknown_pairs_and_missing_controls():
    import json
    from pathlib import Path
    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/evaluation-spec.v3.schema.json"
        ).read_text()
    )
    spec = valid_spec()
    jsonschema.validate(spec, schema)
    spec["variants"]["crypto"] = spec["variants"]["crypto"][1:]
    with pytest.raises(ValueError):
        validate_ablation_spec(spec)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(spec, schema)
