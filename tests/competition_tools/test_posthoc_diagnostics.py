"""Synthetic file-boundary tests; no retained history or model fitting."""

import copy
import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from competition_tools.evaluation.posthoc_reference import evaluate, same


def synthetic():
    calendar = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(110)]
    days = calendar[:40]
    names = [f"c{i}" for i in range(30)]
    observations = [
        [d, n, n, 100.0, 100.0 + (i + j) % 9, True, False]
        for i, d in enumerate(calendar)
        for j, n in enumerate(names)
    ]
    blocks = [
        dict(
            id=f"h{h}-{w}-{m}",
            model=m,
            training_horizon=h,
            window=w,
            sessions=days,
            scores=[
                [d, n, float((i * 3 + j) % 31)]
                for i, d in enumerate(days)
                for j, n in enumerate(names)
            ],
        )
        for h in (5, 20)
        for w in (calendar[0], calendar[40])
        for m in ("ridge", "elastic_net", "shallow_tree", "momentum20")
    ]
    # Every original legacy return is future close / first future open - 1.
    original = [
        [d, n, h, (100.0 + (i + h + j) % 9) / 100 - 1]
        for i, d in enumerate(days)
        for n, j in zip(names, range(30), strict=True)
        for h in (5, 20)
    ]
    return dict(
        schema="equity.posthoc_inputs.v1",
        calendar=calendar,
        cohorts={d: names for d in days},
        observations=observations,
        blocks=blocks,
        original_labels=original,
    )


def test_independent_consumer_and_tampering():
    evidence = synthetic()
    family = [
        dict(block=b["id"], horizon=h)
        for b in evidence["blocks"]
        for h in (1, 5, 10, 20)
    ]
    actual = evaluate(evidence, family)
    expected = copy.deepcopy(actual)
    assert len(actual["hypotheses"]) == 64
    assert all(
        r["uncertainty"]["reason"] == "insufficient_sessions"
        for r in actual["hypotheses"]
        if r["horizon"] == 20
    )
    tampered = copy.deepcopy(actual)
    tampered["hypotheses"][0]["daily"][0]["quintile_counts"][0] += 1
    with pytest.raises(ValueError):
        same(tampered, expected)
    bad = copy.deepcopy(evidence)
    bad["original_labels"][0][3] += 0.01
    with pytest.raises(ValueError, match="ORIGINAL_LABEL"):
        evaluate(bad, family)
    with pytest.raises(ValueError, match="FAMILY"):
        evaluate(evidence, family[:-1])
    with pytest.raises(ValueError):
        json.dumps(actual | {"bad": float("nan")}, allow_nan=False)


@pytest.mark.skipif(
    not os.environ.get("POSTHOC_LEAF_PYTHON"),
    reason="explicit separate leaf environment required",
)
def test_complete_synthetic_file_workflow(tmp_path, monkeypatch):
    from competition_tools.evaluation import posthoc_diagnostics as workflow

    evidence = synthetic()
    monkeypatch.setattr(
        workflow, "saved_inputs", lambda _: (evidence, {"tree_protocol": "synthetic"})
    )
    monkeypatch.setattr(
        workflow,
        "source_record",
        lambda _: {
            "identity": {"source_root": str(Path(__file__).resolve().parents[2])}
        },
    )
    monkeypatch.setattr(workflow, "canonical_location", lambda p: Path(p).resolve())
    owner, output = tmp_path / "owner", tmp_path / "result"
    frozen = workflow.prepare("synthetic", owner, output, "synthetic")
    assert not output.exists()
    result = workflow.run(frozen["protocol"], os.environ["POSTHOC_LEAF_PYTHON"])
    assert result["family_size"] == 64
    assert (output / "producer-started.json").is_file()
    assert result == workflow.verify(frozen["protocol"])
    with pytest.raises(FileExistsError):
        workflow.run(frozen["protocol"], os.environ["POSTHOC_LEAF_PYTHON"])
    report = json.loads((output / "report.json").read_text())
    report["hypotheses"][0]["daily"][0]["coverage"] = 0.123
    (output / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="ARITHMETIC"):
        workflow.verify(frozen["protocol"])
    (owner / "inputs.json").write_text("{}")
    with pytest.raises(ValueError, match="INPUT_HASH"):
        workflow.check_protocol(frozen["protocol"])


def test_saved_report_schema_is_closed():
    from jsonschema import validate, ValidationError

    evidence = synthetic()
    family = [
        dict(block=b["id"], horizon=h)
        for b in evidence["blocks"]
        for h in (1, 5, 10, 20)
    ]
    report = dict(binding_sha256="0" * 64, **evaluate(evidence, family))
    base = Path(__file__).resolve().parents[2] / "schemas/research"
    schema = json.loads((base / "posthoc-diagnostics.v1.schema.json").read_text())
    validate(report, schema)
    report["hypotheses"][0]["uncertainty"]["invented"] = 1
    with pytest.raises(ValidationError):
        validate(report, schema)


def test_reference_math_nonfinite_gaps_and_constant():
    from competition_tools.evaluation.posthoc_reference import statistics, daily

    values, grid = [-1.0, 1.0] * 20, list(range(40))
    assert statistics(values, 1, grid, grid)["se"] == pytest.approx((1 / 39) ** 0.5)
    assert statistics(values, 20, grid, grid)["reason"] == "insufficient_sessions"
    assert statistics([0.1] * 40, 1, grid, grid)["reason"] == "constant_daily_ic"
    assert (
        statistics(values[:-1] + [None], 1, grid, grid)["reason"]
        == "missing_or_nonfinite_daily_ic"
    )
    assert (
        statistics(values, 1, grid, grid[:20] + ["gap"] + grid[20:])["reason"]
        == "noncontiguous_calendar"
    )
    assert (
        daily([None] + list(range(30)), list(range(31)))["ic_reason"]
        == "missing_predictions"
    )


def test_source_reparse_rejected_before_resolving(monkeypatch, tmp_path):
    from competition_tools.evaluation import posthoc_diagnostics as workflow

    monkeypatch.setattr(Path, "is_junction", lambda p: p == tmp_path, raising=False)
    with pytest.raises(ValueError, match="REPARSE"):
        workflow.source_record(tmp_path)


def test_reference_pricing_interval_excludes_decision_ohlc():
    from competition_tools.evaluation.posthoc_reference import label

    observations = {
        (0, "a"): ["OLD", None, None, False, True],
        (1, "a"): ["NEW", 10.0, 11.0, True, False],
    }
    assert label(observations, [0, 1], 0, "a", 1) == pytest.approx(0.1)
