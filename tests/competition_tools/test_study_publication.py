"""Publication consumes verified private artifacts and emits allowlisted facts."""

import json
import pytest
from competition_tools.evaluation.study_plan import freeze_study
from competition_tools.evaluation.study_runner import run_study
from competition_tools.evaluation.study_publication import project_study
from competition_tools.evaluation.study_publication import validate_public_study
from competition_tools.team.config import TeamConfig
from test_study_plan import crypto_manifest, identity, COSTS


def blocked_study(tmp_path):
    manifest = crypto_manifest(tmp_path / "data", days=300)
    freeze_study(
        dict(
            schema="competition.evaluation_spec.v2",
            manifests=[str(manifest)],
            costs=COSTS,
        ),
        tmp_path / "plan",
        code_identity=identity(tmp_path / "code"),
    )
    return run_study(
        TeamConfig(tmp_path, tmp_path / "envs"), tmp_path / "plan/plan.json"
    )


def test_private_metadata_is_not_projected(tmp_path):
    aggregate = blocked_study(tmp_path)
    aggregate["private"] = {"account": "PRIVATE_SENTINEL", "path": "C:/private/raw.csv"}
    aggregate["jobs"][0]["private"] = "PRIVATE_SENTINEL"
    projected = project_study(aggregate)
    encoded = json.dumps(projected)
    assert "PRIVATE_SENTINEL" not in encoded and "C:/private" not in encoded
    assert set(projected) == set(
        "schema as_of code_commit plan_sha256 methods coverage results blockers".split()
    )
    assert all(
        r["net_return"] is None and r["status"] == "blocked"
        for r in projected["results"]
    )


@pytest.mark.parametrize("mutation", ["extra", "product", "nonfinite", "nested"])
def test_public_document_rejects_unsafe_fields(tmp_path, mutation):
    value = project_study(blocked_study(tmp_path))
    if mutation == "extra":
        value["private_path"] = "C:/private"
    elif mutation == "product":
        value["coverage"][0]["products"] = ["PRIVATE_SENTINEL"]
    elif mutation == "nonfinite":
        value["results"][0]["net_return"] = float("nan")
    else:
        value["results"][0]["private"] = {"secret": "PRIVATE_SENTINEL"}
    with pytest.raises(ValueError):
        validate_public_study(value)


@pytest.mark.parametrize(
    "mutation", ["hash", "code", "forged_completed", "missing_job", "private_product"]
)
def test_tampered_aggregate_cannot_publish(tmp_path, mutation):
    aggregate = blocked_study(tmp_path)
    if mutation == "hash":
        aggregate["plan_sha256"] = "f" * 64
    elif mutation == "code":
        aggregate["code_commit"] = "e" * 40
    elif mutation == "missing_job":
        aggregate["jobs"].pop()
    elif mutation == "private_product":
        p = tmp_path / "plan/plan.json"
        value = json.loads(p.read_text())
        value["inputs"][0]["products"] = ["PRIVATE_SENTINEL"]
        p.write_text(json.dumps(value))
    else:
        aggregate["jobs"][0].update(status="completed", metrics={"net_return": 0})
    with pytest.raises(ValueError):
        project_study(aggregate)
