"""The root consumer verifies producer facts instead of importing research."""

import copy
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError
from pathlib import Path

from competition_tools.check_workflow_delivery import (
    synthetic_jobs,
    validate_leaf_result,
    package_digest,
)
from competition_tools.evaluation.run_record import init_run


@pytest.fixture
def leaf(tmp_path):
    run = init_run(tmp_path / "run")
    (run / "inputs").mkdir()
    job = synthetic_jobs()["crypto-mm"]
    path = run / "inputs/crypto-mm.json"
    path.write_text(json.dumps(job))
    source = run / "source/source/research/crypto-mm/src/crypto_mm"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE=1\n")
    folder = run / "crypto-mm"
    folder.mkdir()
    evidence = dict(prices={}, net={}, gross={})
    value = dict(
        schema="competition.workflow_leaf_result.v1",
        status="completed",
        project="crypto-mm",
        synthetic=True,
        accounting_model="self_financing_daily.v1",
        quote_currency="USDT",
        initial_equity=1,
        parameters=job["parameters"],
        input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        code_sha256=package_digest(source),
        environment=dict(
            python="3.12.0", distributions={"competition-crypto-mm": "0.1.0"}
        ),
        metrics={},
        evidence=evidence,
        artifacts=[],
    )
    for name in (
        "prices.json",
        "targets.json",
        "net.json",
        "gross.json",
        "summary.json",
    ):
        path = folder / name
        path.write_text("{}")
        value["artifacts"].append(
            dict(
                path=name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                bytes=path.stat().st_size,
            )
        )
    (folder / "result.json").write_text(json.dumps(value))
    return run, job, dict(code=dict(source_root="source/source")), value


def test_root_accepts_consistent_producer_metadata_without_leaf_import(leaf):
    run, job, plan, value = leaf
    assert validate_leaf_result(run, "crypto-mm", job, plan) == value


@pytest.mark.parametrize(
    "field, bad",
    [
        ("code_sha256", "0" * 64),
        ("input_sha256", "0" * 64),
        ("synthetic", 1),
        ("project", "equity-lab"),
        ("status", "failed"),
        ("quote_currency", "USD"),
    ],
)
def test_mismatched_producer_identity_is_rejected(leaf, field, bad):
    run, job, plan, value = leaf
    value[field] = bad
    (run / "crypto-mm/result.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        validate_leaf_result(run, "crypto-mm", job, plan)


def test_changed_artifact_and_divergent_embedded_evidence_are_rejected(leaf):
    run, job, plan, value = leaf
    original = copy.deepcopy(value)
    value["evidence"]["net"] = {"different": True}
    (run / "crypto-mm/result.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        validate_leaf_result(run, "crypto-mm", job, plan)
    (run / "crypto-mm/result.json").write_text(json.dumps(original))
    (run / "crypto-mm/net.json").write_text('{"changed":true}')
    with pytest.raises(ValueError):
        validate_leaf_result(run, "crypto-mm", job, plan)


def test_child_cannot_supply_arbitrary_artifact_paths(leaf):
    run, job, plan, value = leaf
    value["artifacts"][0]["path"] = "../outside.json"
    (run / "crypto-mm/result.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        validate_leaf_result(run, "crypto-mm", job, plan)


@pytest.mark.parametrize("bad", ["nonfinite", "duplicate_key"])
def test_result_json_must_be_finite_and_unambiguous(leaf, bad):
    run, job, plan, value = leaf
    if bad == "nonfinite":
        value["metrics"]["extra"] = float("nan")
        path = run / "crypto-mm/summary.json"
        path.write_text(json.dumps(value["metrics"]))
        artifact = next(a for a in value["artifacts"] if a["path"] == "summary.json")
        artifact.update(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            bytes=path.stat().st_size,
        )
    body = json.dumps(value)
    if bad == "duplicate_key":
        body = '{"schema":"ignored-duplicate",' + body[1:]
    (run / "crypto-mm/result.json").write_text(body)
    with pytest.raises(ValueError):
        validate_leaf_result(run, "crypto-mm", job, plan)


def test_fictional_job_inputs_are_deterministic_and_independent():
    jobs = synthetic_jobs()
    assert jobs == synthetic_jobs()
    assert set(jobs) == {"equity-lab", "crypto-mm"}
    assert all(j["synthetic"] is True for j in jobs.values())
    assert len(jobs["crypto-mm"]["data"]["dates"]) == 270


def test_published_schema_agrees_with_producer_identity_contract(leaf):
    _, _, _, value = leaf
    path = (
        Path(__file__).resolve().parents[2]
        / "schemas/research/workflow-leaf-result.v1.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.validate(value)
    for field, bad in (
        ("synthetic", 1),
        ("project", "unknown"),
        ("quote_currency", "USD"),
        ("status", "failed"),
    ):
        altered = copy.deepcopy(value)
        altered[field] = bad
        with pytest.raises(ValidationError):
            validator.validate(altered)
