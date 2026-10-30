"""New workflow rejects incomplete parents and mutable frozen protocols."""

import json
from pathlib import Path

import pytest

from competition_tools.evaluation.tree_study import freeze_parent, verify_binding, rules
from competition_tools.evaluation.study_identity import canonical_hash


def test_no_parent_record_means_no_reuse_or_fit(tmp_path):
    (tmp_path / "equity").mkdir()
    (tmp_path / "input.parquet").write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="RUN_OWNER"):
        freeze_parent(tmp_path, tmp_path / "equity", tmp_path / "input.parquet")
    assert not (tmp_path / "attempts-5.jsonl").exists()


def test_changed_protocol_fails_closed_before_parent_access(tmp_path):
    protocol = dict(
        schema="competition.low_turnover_tree_protocol.v1",
        rules=rules(),
        binding_sha256="0" * 64,
    )
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="PROTOCOL"):
        verify_binding(path)


def test_protocol_rejects_rule_expansion_even_with_recomputed_digest(tmp_path):
    protocol = dict(schema="competition.low_turnover_tree_protocol.v1", rules=rules())
    protocol["rules"]["depths"] = [2, 3, 4]
    protocol["binding_sha256"] = canonical_hash(protocol)
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="PROTOCOL"):
        verify_binding(path)


def test_launch_resolves_frozen_legacy_locations_after_recorded_move(tmp_path):
    from competition_tools.evaluation.tree_study import launch_command

    old = tmp_path / "2026-quant-competition"
    new = tmp_path / "global-market-research"
    new.mkdir()
    (new / ".storage-migration.json").write_text(
        json.dumps(
            dict(
                schema="competition.storage_migration.v1",
                legacy_root=str(old),
                canonical_root=str(new),
                phase="completed",
                inventory_sha256="0" * 64,
            )
        )
    )
    command = launch_command(
        dict(input=str(old / "inputs/daily.parquet"), output=str(old / "results/tree")),
        old / "research-reservations/run.json",
        Path("python"),
    )
    assert command[-6:] == [
        "--input",
        str(new / "inputs/daily.parquet"),
        "--output",
        str(new / "results/tree"),
        "--reservation",
        str(new / "research-reservations/run.json"),
    ]


def test_completed_or_failed_fit_requires_durable_start_except_pre_fit_budget_exhaustion():
    from competition_tools.evaluation.tree_study_validation import (
        verify_candidate_start,
    )

    with pytest.raises(ValueError, match="START"):
        verify_candidate_start(dict(status="completed", attempt=None, reason=None))
    with pytest.raises(ValueError, match="START"):
        verify_candidate_start(
            dict(status="failed", attempt=None, reason="ValueError: labels")
        )
    verify_candidate_start(
        dict(status="failed", attempt=None, reason="RuntimeError: Fit budget exhausted")
    )
    verify_candidate_start(dict(status="completed", attempt=1, reason=None))


@pytest.mark.parametrize(
    "model,status,end",
    [
        ("momentum20", "failed", "2026-07-24"),
        ("shallow_tree", "completed", "2026-07-23"),
        ("momentum20", "completed", "2026-07-23"),
    ],
)
def test_model_metadata_cannot_change_window_or_completion_state(model, status, end):
    from competition_tools.evaluation.tree_study_validation import verify_model_identity

    with pytest.raises(ValueError):
        verify_model_identity(dict(model=model, status=status, end=end), "2026-07-24")


def test_root_study_modules_import_only_standard_library_and_root_code():
    import ast
    import sys

    root = Path(__file__).resolve().parents[2] / "src/competition_tools/evaluation"
    for name in ("tree_study.py", "tree_study_validation.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    n.name.split(".")[0] in sys.stdlib_module_names for n in node.names
                )
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert node.module.split(".")[0] in sys.stdlib_module_names
