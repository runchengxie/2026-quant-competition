from __future__ import annotations

import json
from pathlib import Path

import pytest

from strategies.nira.handoff import (
    HandoffValidationError,
    NiraTargetHandoff,
    load_target_artifact,
    write_target_artifact,
)


def target_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "strategy_id": "japanese-nira",
        "market": "JP",
        "as_of": "2026-09-03T00:00:00Z",
        "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "1"}],
    }


def lineage_payload() -> dict[str, object]:
    return {
        "lineage_version": "1.0",
        "source": "nira",
        "source_revision": "abc123",
        "generated_at": "2026-09-03T00:01:00Z",
        "signal_artifact": "signals/xgb_daily_optuna_lite.parquet",
        "research_run_id": "run-42",
    }


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_target_artifact_validates_contract_and_preserves_lineage(
    tmp_path: Path,
) -> None:
    targets_path = tmp_path / "targets.json"
    lineage_path = tmp_path / "lineage.json"
    write_json(targets_path, target_payload())
    write_json(lineage_path, lineage_payload())

    handoff = load_target_artifact(targets_path, lineage_path=lineage_path)

    assert isinstance(handoff, NiraTargetHandoff)
    assert handoff.target_set.strategy_id == "japanese-nira"
    assert handoff.target_set.targets[0].symbol == "1321.T"
    assert handoff.lineage == lineage_payload()
    assert handoff.target_path == targets_path
    assert handoff.lineage_path == lineage_path


def test_loader_accepts_embedded_lineage_without_importing_research_code(
    tmp_path: Path,
) -> None:
    payload = target_payload()
    payload["lineage"] = lineage_payload()
    target_path = tmp_path / "targets-with-lineage.json"
    write_json(target_path, payload)

    handoff = load_target_artifact(target_path)

    assert handoff.lineage == lineage_payload()
    assert handoff.target_set.to_dict() == target_payload()


def test_loader_accepts_lineage_in_a_small_artifact_envelope(tmp_path: Path) -> None:
    target_path = tmp_path / "bundle.json"
    write_json(
        target_path,
        {"target_set": target_payload(), "lineage": lineage_payload()},
    )

    handoff = load_target_artifact(target_path)

    assert handoff.target_set.to_dict() == target_payload()
    assert handoff.lineage == lineage_payload()


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"not": "an object"}, "unknown root field"),
        ({**target_payload(), "lineage": []}, "lineage must be an object"),
    ],
)
def test_loader_rejects_malformed_target_or_lineage_payload(
    tmp_path: Path, payload: dict[str, object], message: str
) -> None:
    target_path = tmp_path / "targets.json"
    write_json(target_path, payload)

    with pytest.raises(HandoffValidationError, match=message):
        load_target_artifact(target_path)


def test_loader_rejects_lineage_that_is_not_a_json_object(tmp_path: Path) -> None:
    targets_path = tmp_path / "targets.json"
    lineage_path = tmp_path / "lineage.json"
    write_json(targets_path, target_payload())
    write_json(lineage_path, ["not", "metadata"])

    with pytest.raises(HandoffValidationError, match="lineage must be an object"):
        load_target_artifact(targets_path, lineage_path=lineage_path)


def test_loader_rejects_null_embedded_lineage(tmp_path: Path) -> None:
    target_path = tmp_path / "targets.json"
    payload = target_payload()
    payload["lineage"] = None
    write_json(target_path, payload)

    with pytest.raises(HandoffValidationError, match="lineage must be an object"):
        load_target_artifact(target_path)


def test_write_target_artifact_is_atomic_and_writes_normalized_consumable_files(
    tmp_path: Path,
) -> None:
    targets_path = tmp_path / "out" / "targets.json"
    lineage_path = tmp_path / "out" / "lineage.json"
    handoff = NiraTargetHandoff.from_payload(target_payload(), lineage_payload())

    write_target_artifact(handoff, targets_path, lineage_path=lineage_path)

    loaded = load_target_artifact(targets_path, lineage_path=lineage_path)
    assert loaded.target_set == handoff.target_set
    assert loaded.lineage == handoff.lineage
    assert json.loads(targets_path.read_text(encoding="utf-8")) == target_payload()
    assert json.loads(lineage_path.read_text(encoding="utf-8")) == lineage_payload()
    assert not list(targets_path.parent.glob("*.tmp"))


def test_write_target_artifact_does_not_overwrite_lineage_by_default(
    tmp_path: Path,
) -> None:
    targets_path = tmp_path / "targets.json"
    lineage_path = tmp_path / "lineage.json"
    write_json(lineage_path, {"keep": "me"})
    handoff = NiraTargetHandoff.from_payload(target_payload(), lineage_payload())

    with pytest.raises(FileExistsError):
        write_target_artifact(handoff, targets_path, lineage_path=lineage_path)


def test_source_tree_is_not_a_runtime_dependency() -> None:
    import ast

    source = Path(__file__).parents[2] / "strategies" / "nira"
    imported_modules: list[str] = []
    for path in source.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules.extend(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        imported_modules.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

    assert not any(
        "research_workspace" in module or "nira" in module.lower() and module != "strategies.nira.handoff"
        for module in imported_modules
    )
