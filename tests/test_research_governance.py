from datetime import datetime, timezone, timedelta
import copy
import json
from pathlib import Path
import pytest

from competition_tools import research_governance as g


def test_six_work_items_bind_broad_input_and_cannot_accept():
    work = g.evidence_worklist()
    assert len(work["items"]) == 6
    assert work["input_sha256"] == g.INPUT_SHA256
    assert work["scope"]["monthly_candidates"] == 500
    for item in work["items"]:
        assert all(
            item[k]
            for k in ("owner_role", "material", "validation", "reject", "next_action")
        )
        assert item["status"] == "blocked_external"
    assert work["accepted_research"] is False


def test_future_intent_boundary_and_immutable_registration(tmp_path):
    intent = g.future_intent(
        datetime(2026, 11, 2, 15, tzinfo=timezone.utc),
        [
            {
                "session": (datetime(2026, 11, 2) + timedelta(days=i))
                .date()
                .isoformat(),
                "open_at": (
                    datetime(2026, 11, 2, 14, 30, tzinfo=timezone.utc)
                    + timedelta(days=i)
                ).isoformat(),
            }
            for i in range(141)
        ],
        {"source": "a" * 40, "root_lock": "b" * 64, "equity_lock": "c" * 64},
    )
    assert intent["first_eligible_session"] == "2026-11-03"
    assert intent["future_authorized_fit_cap"] == 0
    assert intent["evaluation_sessions"] == 120 and intent["label_tail_sessions"] == 20
    target = tmp_path / "intent.json"
    g.register_intent(target, intent)
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        g.register_intent(target, intent)
    assert target.read_bytes() == original
    forged = copy.deepcopy(intent)
    forged["observation_import_enabled"] = True
    with pytest.raises(ValueError):
        g.register_intent(tmp_path / "forged.json", forged)
    forged = copy.deepcopy(intent)
    forged["evaluation_sessions"] = 2
    forged["intent_sha256"] = g.digest(
        {k: v for k, v in forged.items() if k != "intent_sha256"}
    )
    with pytest.raises(ValueError):
        g.register_intent(tmp_path / "short.json", forged)


def test_execution_self_certification_never_lifts_gate():
    intake = g.execution_template()
    assert g.validate_execution(intake)["status"] == "blocked_external"
    intake["synthetic"] = True
    assert g.validate_execution(intake)["status"] == "diagnostic_only"
    intake["verified"] = True
    with pytest.raises(ValueError):
        g.validate_execution(intake)


def test_public_status_closed_and_bound_to_reviewed_facts():
    payload = g.public_status()
    g.validate_public_status(payload)
    payload["forest_status"] = "completed"
    with pytest.raises(ValueError):
        g.validate_public_status(payload)


def test_public_status_source_provenance_is_canonical():
    root = Path(__file__).resolve().parents[1]
    tree = json.loads((root / "site/src/data/tree-study.v1.json").read_text())
    assert (
        g.digest(tree)
        == g.public_status()["source_facts"]["tree_study_canonical_sha256"]
    )


def test_pages_checker_accepts_new_closed_status_sources():
    from competition_tools.check_pages_content import _allowed_source
    from pathlib import PurePosixPath

    assert _allowed_source(PurePosixPath("src/data/research-progress.v1.json"))
    assert _allowed_source(PurePosixPath("src/i18n/progress-en.json"))
    assert not _allowed_source(PurePosixPath("src/data/arbitrary-private.json"))


def test_rendered_progress_metadata_parses_exact_facts():
    from competition_tools.check_pages_content import _PageMetadata
    import html

    metadata = _PageMetadata()
    metadata.feed(
        '<main data-next-stage-facts="'
        + html.escape(json.dumps(g.public_status()), quote=True)
        + '"></main>'
    )
    assert [json.loads(row) for row in metadata.next_stage_facts] == [g.public_status()]


def test_intent_rejects_source_output_and_naive_calendars(tmp_path):
    with pytest.raises(ValueError, match="TIMEZONE"):
        g.future_intent(datetime(2026, 11, 1), [], {})
    with pytest.raises(ValueError, match="INVALID_CALENDAR"):
        g.future_intent(
            datetime(2026, 11, 1, tzinfo=timezone.utc),
            [{"session": "2026-11-02", "open_at": "2026-11-02T14:30:00"}],
            {"source": "a" * 40, "root_lock": "b" * 64, "equity_lock": "c" * 64},
        )
    root = tmp_path / "source"
    root.mkdir()
    (root / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError, match="OUTPUT_IN_SOURCE"):
        g._exclusive_json(root / "out.json", {})


def test_all_material_references_still_require_real_owner_review():
    intake = g.execution_template()
    for group in ("cost_material", "paper_material"):
        intake[group] = dict.fromkeys(intake[group], "self-certified-receipt")
    result = g.validate_execution(intake)
    assert result["missing"] == []
    assert result["status"] == "blocked_external"
    assert result["broker_authorized"] is False


def test_public_status_rejects_boolean_integer_aliases():
    value = g.public_status()
    value["accepted_research"] = 0
    with pytest.raises(ValueError):
        g.validate_public_status(value)


def test_intent_requires_full_future_schedule_and_safe_output(tmp_path):
    with pytest.raises(ValueError, match="INSUFFICIENT_FUTURE"):
        g.future_intent(
            datetime(2026, 11, 1, tzinfo=timezone.utc),
            [{"session": "2026-11-02", "open_at": "2026-11-02T14:30:00+00:00"}],
            {"source": "a" * 40, "root_lock": "b" * 64, "equity_lock": "c" * 64},
        )
    with pytest.raises(ValueError, match="UNSAFE"):
        g._exclusive_json(tmp_path / "unused" / ".." / "out.json", {})


def test_output_rejects_unresolved_junction_ancestor(tmp_path, monkeypatch):
    junction = tmp_path / "alias"
    original = Path.is_junction
    monkeypatch.setattr(
        Path, "is_junction", lambda path: path == junction or original(path)
    )
    with pytest.raises(ValueError, match="UNSAFE"):
        g._exclusive_json(junction / "out.json", {})


def test_public_schema_and_strict_reader(tmp_path):
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "schemas/research/research-progress.v1.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(g.public_status())
    assert g.digest(schema["const"]) == g.digest(g.public_status())
    target = tmp_path / "duplicate.json"
    target.write_text('{"accepted_research":true,"accepted_research":false}')
    with pytest.raises(ValueError, match="DUPLICATE"):
        g.read_json(target)
    target.write_text('{"value":NaN}')
    with pytest.raises(ValueError, match="NONFINITE"):
        g.read_json(target)


def test_worklist_payload_mutation_cannot_change_frozen_scope():
    payload = g.evidence_worklist()
    payload["scope"]["monthly_candidates"] = 10
    assert g.evidence_worklist()["scope"]["monthly_candidates"] == 500


def test_cli_validates_private_execution_intake(tmp_path):
    import os
    import subprocess
    import sys

    source = tmp_path / "intake.json"
    source.write_text(json.dumps(g.execution_template()), encoding="utf8")
    output = tmp_path / "result.json"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "competition_tools.research_governance",
            "validate-execution",
            "--input",
            str(source),
            "--output",
            str(output),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["status"] == "blocked_external"
