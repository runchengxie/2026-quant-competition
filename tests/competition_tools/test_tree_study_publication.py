"""The new public snapshot is closed, complete, internally matched and reviewed."""

import copy
import json
from pathlib import Path

import pytest

from competition_tools.evaluation import tree_study_publication as public


def snapshot():
    return json.loads(
        (Path(__file__).parents[2] / "site/src/data/tree-study.v1.json").read_text()
    )


def test_reviewed_snapshot_and_full_grid():
    value = snapshot()
    assert public.parse_reviewed(json.dumps(value)) == value
    assert len(value["comparisons"]) == 432
    assert len(value["models"]) == 8


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(private_path="D:/private"),
        lambda v: v["models"][0].update(predictions=[]),
        lambda v: v["counts"].update(completed_new_accounts=61),
        lambda v: v["comparisons"][0].update(difference=99),
        lambda v: v["comparisons"][0].update(horizon=7),
        lambda v: v["comparisons"].__setitem__(1, copy.deepcopy(v["comparisons"][0])),
        lambda v: v["comparisons"][0].update(reference_buffer=20),
        lambda v: v["models"][0].update(mean_daily_ic=float("nan")),
    ],
)
def test_semantic_tampering_fails_without_hash_gate(change):
    value = snapshot()
    change(value)
    with pytest.raises(ValueError):
        public.validate(value)


def test_changed_valid_metric_fails_reviewed_hash():
    value = snapshot()
    value["models"][0]["mean_daily_ic"] += 0.001
    public.validate(value)
    with pytest.raises(ValueError, match="REVIEWED"):
        public.parse_reviewed(json.dumps(value))


@pytest.mark.parametrize("raw", ['{"schema":1,"schema":2}', '{"x":NaN}', '{"x":1e999}'])
def test_ambiguous_or_nonfinite_json_fails(raw):
    with pytest.raises(ValueError):
        public.parse_reviewed(raw)


def test_all_unavailable_comparisons_preserve_null_and_reasons():
    for row in snapshot()["comparisons"]:
        if row["arm_status"] == "blocked" or row["reference_status"] == "blocked":
            assert row["difference"] is None
            assert row["reason"] == "unavailable_account"
            assert row["arm_net_return"] is None or row["reference_net_return"] is None


def test_projection_stops_before_reading_unverified_outputs(monkeypatch):
    from competition_tools.evaluation import tree_study_projection as projection

    def reject(protocol):
        raise ValueError("unverified saved result")

    monkeypatch.setattr(projection, "verify", reject)
    with pytest.raises(ValueError, match="unverified saved result"):
        projection.project("missing-protocol.json")


def test_jsonschema_is_closed_and_accepts_reviewed_snapshot():
    import jsonschema

    schema = json.loads(
        (
            Path(__file__).parents[2]
            / "schemas/research/public-tree-study.v1.schema.json"
        ).read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(snapshot(), schema)
    value = snapshot()
    value["comparisons"][0]["ticker"] = "private"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, schema)
