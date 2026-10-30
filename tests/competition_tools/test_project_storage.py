"""Storage names must not select a second authority or reset spent budgets."""

import json
from pathlib import Path

import pytest


def test_fresh_legacy_new_and_ambiguous_roots(tmp_path, monkeypatch):
    from competition_tools.project_storage import project_root

    monkeypatch.delenv("GLOBAL_MARKET_RESEARCH_DATA_ROOT", raising=False)
    assert project_root(tmp_path) == tmp_path / "global-market-research"
    old = tmp_path / "2026-quant-competition"
    old.mkdir()
    assert project_root(tmp_path) == old
    new = tmp_path / "global-market-research"
    new.mkdir()
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        project_root(tmp_path)
    assert project_root(tmp_path, new) == new
    with pytest.raises(ValueError):
        project_root(tmp_path, tmp_path / "other")


def test_project_environment_and_no_reparse_alias(tmp_path, monkeypatch):
    from competition_tools.project_storage import project_root

    new = tmp_path / "global-market-research"
    monkeypatch.setenv("GLOBAL_MARKET_RESEARCH_DATA_ROOT", str(new))
    assert project_root(tmp_path) == new
    monkeypatch.delenv("GLOBAL_MARKET_RESEARCH_DATA_ROOT")
    target = tmp_path / "real"
    target.mkdir()
    try:
        new.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    with pytest.raises(ValueError):
        project_root(tmp_path, new)


def test_recorded_location_mapping_preserves_relative_path(tmp_path):
    from competition_tools.project_storage import relocated_path

    old = tmp_path / "2026-quant-competition"
    new = tmp_path / "global-market-research"
    new.mkdir()
    original = old / "research/output.json"
    assert relocated_path(original) == original
    receipt = dict(
        schema="competition.storage_migration.v1",
        legacy_root=str(old),
        canonical_root=str(new),
        phase="completed",
        inventory_sha256="a" * 64,
    )
    (new / ".storage-migration.json").write_text(json.dumps(receipt))
    assert relocated_path(original) == new / "research/output.json"
    assert receipt["legacy_root"] == str(old)
    receipt["canonical_root"] = str(tmp_path / "other")
    (new / ".storage-migration.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        relocated_path(original)


def test_cross_root_consumed_guard_cannot_be_reset(tmp_path):
    from competition_tools.project_storage import guarded_location

    old = tmp_path / "2026-quant-competition"
    new = tmp_path / "global-market-research"
    marker = old / "authorizations/attempt.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("consumed")
    new.mkdir()
    with pytest.raises(FileExistsError):
        with guarded_location(new, "authorizations/attempt.json"):
            pytest.fail("Existing alternate-root marker must block writing")
    assert marker.read_text() == "consumed"
    assert not (new / "authorizations/attempt.json").exists()


def test_cross_root_lock_excludes_other_writer(tmp_path):
    from competition_tools.project_storage import guarded_location

    old = tmp_path / "2026-quant-competition"
    new = tmp_path / "global-market-research"
    old.mkdir()
    new.mkdir()
    with guarded_location(old, "research-reservations/study.json"):
        with pytest.raises(FileExistsError):
            with guarded_location(new, "research-reservations/study.json"):
                pytest.fail("Same study cannot reserve concurrently in two roots")


def test_team_v2_and_child_root_propagation(tmp_path, monkeypatch):
    from competition_tools.team.config import load_config
    from competition_tools.team.processes import child_environment

    monkeypatch.delenv("GLOBAL_MARKET_RESEARCH_DATA_ROOT", raising=False)
    project = tmp_path / "global-market-research"
    path = tmp_path / "team.toml"
    path.write_text(
        "\n".join(
            [
                'schema_version="competition.team.v2"',
                f"data_root={json.dumps(str(tmp_path))}",
                f"environment_root={json.dumps(str(project / 'environments'))}",
                f"project_data_root={json.dumps(str(project))}",
            ]
        )
    )
    config = load_config(path)
    assert config.storage_root == project
    assert child_environment(config)["GLOBAL_MARKET_RESEARCH_DATA_ROOT"] == str(project)


def test_independent_storage_clients_do_not_drift():
    root = Path(__file__).parents[2]
    expected = (root / "src/competition_tools/project_storage.py").read_bytes()
    for package in ("equity-lab/equity_lab", "crypto-mm/crypto_mm"):
        project, module = package.split("/")
        assert (
            root / "research" / project / "src" / module / "_project_storage.py"
        ).read_bytes() == expected


def test_reservation_alias_cannot_duplicate_consumed_identity(tmp_path):
    from competition_tools.evaluation.research_reservation import reserve_run

    old, new = tmp_path / "2026-quant-competition", tmp_path / "global-market-research"
    identity = {"protocol": "test.frozen.v1", "input_sha256": "a" * 64}
    first = reserve_run(old, identity, old / "first")
    with pytest.raises(FileExistsError):
        reserve_run(new, identity | {"code_sha256": "different"}, new / "second")
    assert first.is_file()


def test_legacy_team_config_remains_legacy_when_existing(tmp_path):
    from competition_tools.team.config import init_config

    old = tmp_path / "2026-quant-competition"
    old.mkdir()
    assert init_config(tmp_path / "team.toml", tmp_path).storage_root == old


def test_team_v2_init_round_trip_and_invalid_explicit_value(tmp_path):
    from competition_tools.team.config import init_config, load_config

    selected = tmp_path / "global-market-research"
    path = tmp_path / "team.toml"
    config = init_config(path, tmp_path, project_data_root=selected)
    assert load_config(path) == config
    assert "competition.team.v2" in path.read_text()
    body = path.read_text().replace(str(selected).replace("\\", "\\\\"), "unrelated")
    path.write_text(body)
    with pytest.raises(ValueError):
        load_config(path)


def test_descendant_owner_cannot_reset_a_reservation(tmp_path):
    from competition_tools.evaluation.research_reservation import reserve_run

    old = tmp_path / "2026-quant-competition/research/equity-lab"
    new = tmp_path / "global-market-research/research/equity-lab"
    identity = {"protocol": "nested.owner.v1", "input_sha256": "a" * 64}
    reserve_run(old, identity, old / "first")
    with pytest.raises(FileExistsError):
        reserve_run(new, identity, new / "second")


def test_reservation_owner_alias_rejected_before_resolve(tmp_path):
    from competition_tools.evaluation.research_reservation import reserve_run

    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    with pytest.raises(ValueError):
        reserve_run(alias, {"protocol": "alias.v1"}, alias / "result")
    assert not (actual / "research-reservations").exists()


def test_completed_migration_does_not_recreate_legacy_owner(tmp_path):
    from competition_tools.evaluation.research_reservation import reserve_run

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
                inventory_sha256="a" * 64,
            )
        )
    )
    receipt = reserve_run(old, {"protocol": "moved.v1"}, old / "run")
    assert receipt.parent == new / "research-reservations"
    assert not old.exists()


def test_descendant_alias_locks_exclude_concurrent_writers(tmp_path):
    from competition_tools.project_storage import guarded_location

    old = tmp_path / "2026-quant-competition/research/equity-lab"
    new = tmp_path / "global-market-research/research/equity-lab"
    with guarded_location(old, "research-reservations/example.json.started"):
        with pytest.raises(FileExistsError):
            with guarded_location(new, "research-reservations/example.json.started"):
                pytest.fail("Descendant aliases must share one claim lock")
